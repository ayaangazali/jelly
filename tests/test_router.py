"""The router against the stub frontier: what a client and the dashboard would notice breaking."""

import json
import uuid

import httpx
import pytest

from conftest import SERVER_KEY, assert_shape, assert_trace, example, jsonl
from graduate.router import metrics

MESSAGES = [{"role": "user", "content": "The test tests/test_mod_05.py is failing."}]


@pytest.fixture
def sid():
    return "sess-" + uuid.uuid4().hex[:12]


def post(router, sid, **body):
    return router(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {sid}"},
        json={"model": "graduate", "messages": MESSAGES, **body},
    )


def test_json_passthrough_byte_for_byte(router, stub, sid):
    r = post(router, sid)
    assert r.status_code == 200 and r.content == stub.body()
    assert r.headers["content-type"] == "application/json"


@pytest.mark.parametrize("tools", [False, True])
def test_stream_passthrough_in_order(router, stub, sid, tools):
    stub.tools = tools
    r = post(router, sid, stream=True)
    assert r.status_code == 200 and r.content == b"".join(stub.sse())
    assert r.headers["content-type"].startswith("text/event-stream")
    sent = stub.requests[-1][1]
    assert sent["stream_options"] == {"include_usage": True}  # else no usage chunk


def test_bearer_never_forwarded(router, stub, sid, workdir):
    post(router, sid, stream=True)
    headers, sent = stub.requests[-1]
    assert headers["authorization"] == f"Bearer {SERVER_KEY}"
    assert sid not in json.dumps(sent) + str(headers.raw)
    on_disk = "".join(p.read_text() for p in workdir.rglob("*") if p.is_file())
    assert sid in on_disk and SERVER_KEY not in on_disk  # logged, but never the key


@pytest.mark.parametrize("stream", [False, True])
def test_max_tokens_sent_as_max_completion_tokens(router, stub, sid, stream):
    """GPT-5 models reject `max_tokens` on turn 1, and OpenCode sends it (#115)."""
    assert post(router, sid, stream=stream, max_tokens=100).status_code == 200
    sent = stub.requests[-1][1]
    assert sent["max_completion_tokens"] == 100 and "max_tokens" not in sent


@pytest.mark.parametrize("extra", [{}, {"max_tokens": 100}])
def test_max_completion_tokens_kept(router, stub, sid, extra):
    post(router, sid, max_completion_tokens=50, **extra)
    sent = stub.requests[-1][1]
    assert sent["max_completion_tokens"] == 50 and "max_tokens" not in sent


def test_extra_body_merged_over_request(router, stub, sid, monkeypatch):
    """Fast mode: OPENAI_EXTRA_BODY overrides OpenCode's reasoning_effort, which GPT-5.x rejects beside tools."""
    monkeypatch.setenv(
        "OPENAI_EXTRA_BODY", '{"service_tier":"priority","reasoning_effort":"none"}'
    )
    assert post(router, sid, reasoning_effort="medium").status_code == 200
    sent = stub.requests[-1][1]
    assert sent["service_tier"] == "priority" and sent["reasoning_effort"] == "none"
    assert sent["messages"] == MESSAGES


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [400, 429, 500, 503])
def test_upstream_errors_unchanged_and_unlogged(
    router, stub, sid, workdir, status, stream
):
    err = b'{"error": {"message": "stub says no", "type": "rate_limit"}}'
    stub.fail = (status, err)
    r = post(router, sid, stream=stream)
    assert (r.status_code, r.content) == (status, err)
    assert (
        not (workdir / "metrics.jsonl").exists() and not (workdir / "sessions").exists()
    )


def test_unreachable_frontier_is_502(router, stub, sid):
    stub.fail = httpx.ConnectError("connection refused")
    r = post(router, sid)
    assert r.status_code == 502 and r.json()["error"]["type"] == "upstream_error"


@pytest.mark.parametrize("body", [b"{not json", b"[]", b'"hi"', b""])
def test_non_object_body_is_400_and_never_forwarded(router, stub, sid, workdir, body):
    r = router(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {sid}"},
        content=body,
    )
    assert r.status_code == 400 and r.json()["error"]["type"] == "invalid_request_error"
    assert not stub.requests and not list(
        workdir.iterdir()
    )  # no upstream call, session, metric or trace


@pytest.mark.parametrize("tools", [False, True])
@pytest.mark.parametrize("stream", [False, True])
def test_call_logged_in_contract_shapes(router, stub, sid, workdir, stream, tools):
    stub.tools = tools
    post(router, sid, stream=stream)
    usage = {"input_tokens": 1400, "cached_input_tokens": 1280, "output_tokens": 60}

    [line] = jsonl(workdir / f"sessions/{sid}.jsonl")
    assert_shape(line, example("fixtures/session.example.jsonl"))
    # as the client sent it: its model name, no stream_options the router added
    assert line["request"] == {
        "model": "graduate",
        "messages": MESSAGES,
        "stream": stream,
    }
    assert line["response"] == stub.message()  # streamed deltas reassembled
    assert (line["upstream"], line["usage"]) == ("frontier", usage)

    [rec] = jsonl(workdir / "metrics.jsonl")
    assert_shape(rec, example("fixtures/metrics.example.jsonl"))
    assert rec["tool_calls"] == (2 if tools else 0) and rec["stream"] is stream
    assert rec["cost_usd"] == metrics.cost(usage, "frontier") > 0

    agg = router("GET", f"/api/sessions/{sid}").json()
    assert (agg["turns"], agg["input_tokens"], agg["cost_usd"]) == (
        1,
        1400,
        rec["cost_usd"],
    )
    assert router("GET", f"/api/sessions/{sid}/log").json() == [line]
    # Subset: routing (#20) adds its own Memorable and registry.json events.
    assert {e["who"] for e in assert_trace()} >= {
        "Router → OpenAI",
        "Router → Metrics",
        "Router → Session log",
    }


def test_title_call_first_still_classified_by_registered_session(router, stub, sid):
    """OpenCode's first call is often its title request; the session keeps the runner's task type and prompt (#20)."""
    title = [{"role": "user", "content": "Generate a title for this conversation: ..."}]
    task = "The test tests/test_mod_09.py is failing. Fix the code so it passes."
    router(
        "POST",
        "/api/sessions",
        json={"session_id": sid, "prompt": task, "task_type": "fix-failing-test"},
    )
    router(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {sid}"},
        json={"model": "graduate", "messages": title},
    )
    assert (
        router("GET", f"/api/sessions/{sid}").json()["task_type"] == "fix-failing-test"
    )
    # No hint: the registered prompt is classified, not the title request.
    other = "sess-" + uuid.uuid4().hex[:12]
    reg = router("POST", "/api/sessions", json={"session_id": other, "prompt": task})
    assert reg.json()["task_type"].startswith("the-test")  # the runner's GBrain page name, before any model call
    router(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {other}"},
        json={"model": "graduate", "messages": title},
    )
    assert (
        router("GET", f"/api/sessions/{other}")
        .json()["task_type"]
        .startswith("the-test")
    )


def test_no_key_says_how_to_fix_it(router, stub, sid, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    for stream in (False, True):
        r = post(router, sid, stream=stream)
        assert r.status_code == 401 and "graduate init" in r.json()["error"]["message"]
    assert stub.requests == []  # nothing left the machine


@pytest.mark.parametrize("key", ["sk-QWZXPLMK\r", "sk-QWZX\nPLMK", "sk-QWZX\u2019PLMK"])
def test_a_pasted_control_character_never_puts_the_key_in_an_error(
    router, stub, sid, workdir, monkeypatch, key
):
    """A key sourced from a CRLF env file: httpx's header error quotes the whole Authorization value."""
    import socket
    import threading

    from graduate.router import upstream

    s = socket.create_server(
        ("127.0.0.1", 0)
    )  # a real socket: headers are validated on the way out
    threading.Thread(
        target=lambda: [s.accept()[0].close() for _ in iter(int, 1)], daemon=True
    ).start()
    monkeypatch.setattr(upstream, "client", httpx.AsyncClient())
    monkeypatch.setattr(
        upstream, "URL", f"http://127.0.0.1:{s.getsockname()[1]}/v1/chat/completions"
    )
    monkeypatch.setenv("OPENAI_API_KEY", key)
    r = post(router, sid)
    on_disk = "".join(p.read_text() for p in workdir.rglob("*") if p.is_file())
    assert (
        r.status_code in (401, 502)
        and "QWZX" not in r.text + on_disk
        and "PLMK" not in r.text + on_disk
    )


def test_claude_code_messages_stream_through_the_same_path(router, stub, sid, workdir):
    stub.tools = True
    r = router(
        "POST",
        "/v1/messages?beta=true",
        headers={"x-api-key": sid, "x-claude-code-prompt-id": "prompt-1"},
        json={
            "model": "claude-sonnet-4-5",
            "stream": True,
            "max_tokens": 64,
            "system": [{"type": "text", "text": "Be brief."}],
            "tools": [{"name": "read", "input_schema": {"type": "object"}}],
            "messages": [
                {
                    "role": "user",
                    "content": "The test tests/test_mod_05.py is failing.",
                },
                {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "t0", "name": "read", "input": {}}
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "t0", "content": "ok"}
                    ],
                },
            ],
        },
    )
    events = [json.loads(l[5:]) for l in r.text.splitlines() if l.startswith("data:")]
    blocks = [e["content_block"] for e in events if e["type"] == "content_block_start"]
    args = "".join(
        e["delta"]["partial_json"] for e in events if e["type"] == "content_block_delta"
    )
    assert [(b["id"], b["name"]) for b in blocks] == [
        ("call_1", "read"),
        ("call_2", "bash"),
    ]
    assert args == '{"file_path": "calc/mod_05.py"}{"command": "pytest -q"}'
    assert events[-2]["delta"]["stop_reason"] == "tool_use"
    assert events[-2]["usage"] == {
        "input_tokens": 120,
        "cache_read_input_tokens": 1280,
        "output_tokens": 60,
    }
    sent = stub.requests[-1][1]
    assert [m["role"] for m in sent["messages"]] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]
    assert sent["user"] == "prompt-1" and sid not in json.dumps(sent)
    [line] = jsonl(workdir / f"sessions/{sid}.jsonl")
    assert line["request"]["user"] == "prompt-1" and line["response"] == stub.message()
    for bad in (
        b"{not json",
        b"[]",
        b'{"model":"m"}',
        b'{"model":"m","messages":"hi"}',
    ):
        r = router("POST", "/v1/messages", headers={"x-api-key": sid}, content=bad)
        assert (
            r.status_code == 400
            and r.json()["error"]["type"] == "invalid_request_error"
        ), (bad, r.status_code)


def test_truncated_metrics_line_is_skipped_and_the_next_record_survives(workdir):
    good = example("fixtures/metrics.example.jsonl")
    (workdir / "metrics.jsonl").write_text(json.dumps(good) + "\n" + '{"session_id": "sess-trunc", "tur', encoding="utf-8")
    metrics._sessions.clear()
    metrics._load()
    assert metrics.get_session(good["session_id"])["turns"] == 1
    later = dict(good, session_id="sess-later")
    with open("metrics.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(later) + "\n")
    metrics._sessions.clear()
    metrics._load()
    assert metrics.get_session("sess-later")["turns"] == 1


def test_bad_extra_body_still_reaches_the_frontier(router, stub, sid, monkeypatch):
    monkeypatch.setenv("OPENAI_EXTRA_BODY", "not json")
    assert post(router, sid).status_code == 200
    monkeypatch.setenv("OPENAI_EXTRA_BODY", "[1]")
    assert post(router, sid).status_code == 200
    assert len(stub.requests) == 2


def test_a_route_that_raises_hands_the_call_to_the_frontier(router, stub, sid, monkeypatch):
    from graduate.router import app

    def broken(session_id, request):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "memorable output")

    monkeypatch.setattr(app, "_routes", [broken, *app._routes])
    assert post(router, sid).status_code == 200
    assert len(stub.requests) == 1


def test_frontier_calls_are_priced_as_the_model_the_router_sends(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    got = subprocess.run(
        [sys.executable, "-c", "from graduate.router import metrics; print(metrics.PRICES['frontier'])"],
        cwd=tmp_path,
        env={**os.environ, "OPENAI_MODEL": "gpt-5-mini", "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
    )
    assert got.stdout.strip() == str({"model": "gpt-5-mini", "input": 0.25, "cached_input": 0.025, "output": 2.0}), got.stderr
