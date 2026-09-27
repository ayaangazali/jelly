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
    assert {e["who"] for e in assert_trace()} == {
        "Router → OpenAI",
        "Router → Metrics",
        "Router → Session log",
    }
