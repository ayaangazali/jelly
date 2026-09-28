"""POST /api/chat-compare: both models start together, events are tagged per side, the public caps refuse."""

import json
import time
from types import SimpleNamespace

import pytest

from graduate.registrar import train
from graduate.router import chat_api
from conftest import SERVER_KEY, jsonl


class FakeRiver:
    """River's checkpoint chat: answers after `delay` seconds, records when each call came in and what it asked."""

    def __init__(self, delay=0.4, status=200):
        self.delay, self.status, self.calls = delay, status, []

    def chat_complete_from_checkpoint(self, messages, **kw):
        self.calls.append((time.monotonic(), messages, kw))
        time.sleep(self.delay)
        body = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_content": "Owned answer.",
                    }
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        }
        return SimpleNamespace(status_code=self.status, response_json=json.dumps(body))


@pytest.fixture
def river(monkeypatch):
    fake = FakeRiver()
    monkeypatch.setenv("RIVER_API_KEY", "rk-secret-river-key-123")
    monkeypatch.setattr(train.RiverBackend, "_client", lambda self: fake)
    return fake


def events(resp):
    return [json.loads(l[5:]) for l in resp.text.splitlines() if l.startswith("data:")]


def test_both_sides_start_together_and_every_event_is_tagged(router, stub, river):
    big_at = []
    handle = stub.handle

    async def timed(request):
        big_at.append(time.monotonic())
        return await handle(request)

    stub.handle = timed  # the MockTransport holds the bound method; re-point it
    chat_api.upstream.client._transport.handler = timed
    r = router("POST", "/api/chat-compare", json={"preset": "broken-09"})
    assert r.status_code == 200 and r.headers["content-type"].startswith(
        "text/event-stream"
    )
    ev = events(r)
    # River took 0.4 s; the frontier call went out within 0.1 s of River's, not after it.
    assert big_at and river.calls and abs(big_at[0] - river.calls[0][0]) < 0.1
    starts = [e for e in ev if e.get("type") == "start"]
    assert {e["side"] for e in starts} == {"big", "small"} and all(
        e["t_ms"] < 100 for e in starts
    )
    first_done = next(i for i, e in enumerate(ev) if e.get("type") == "done")
    assert max(ev.index(e) for e in starts) < first_done
    assert ev[-1] == {"type": "end"}
    assert all(e["side"] in ("big", "small") for e in ev[:-1])
    text = {
        s: "".join(e["text"] for e in ev if e.get("side") == s and e["type"] == "delta")
        for s in ("big", "small")
    }
    assert text == {"big": "Fixed.", "small": "Owned answer."}
    done = {e["side"]: e for e in ev if e.get("type") == "done"}
    assert done["big"]["output_tokens"] == 60 and done["big"]["input_tokens"] == 1400
    assert done["small"]["output_tokens"] == 3 and done["small"]["cost_usd"] > 0
    # Output capped at 400 tokens on both sides.
    assert (
        stub.requests[0][1]["max_completion_tokens"] == 400
        and river.calls[0][2]["max_tokens"] == 400
    )
    # Logged like any call: one metrics row per side, the budget file counts the request and its cost.
    rows = jsonl("metrics.jsonl")
    assert sorted(x["upstream"] for x in rows) == ["frontier", "owned"]
    budget = json.loads(chat_api.BUDGET_PATH.read_text())
    assert budget["requests"] == 1 and budget["cost_usd"] == round(
        done["big"]["cost_usd"] + done["small"]["cost_usd"], 6
    )


def test_caps_refuse_long_or_empty_prompts_and_a_spent_budget_in_plain_words(router, stub, river):
    r = router("POST", "/api/chat-compare", json={"prompt": "x" * 2001})
    assert r.status_code == 400 and r.json()["error"] == "Keep it under 2,000 characters."
    r = router("POST", "/api/chat-compare", json={"prompt": "   "})
    assert r.status_code == 400 and "{" not in r.json()["error"]
    chat_api.BUDGET_PATH.write_text(json.dumps({"requests": 200, "cost_usd": 0.1}))
    r = router("POST", "/api/chat-compare", json={"prompt": "say anything"})
    assert r.status_code == 429 and r.json()["error"] == "Demo budget reached, try again later."
    chat_api.BUDGET_PATH.write_text(json.dumps({"requests": 3, "cost_usd": 4.999}))
    r = router("POST", "/api/chat-compare", json={"preset": "broken-09"})
    assert r.status_code == 429 and r.json()["error"] == "Demo budget reached, try again later."
    assert not stub.requests and not river.calls  # a refusal spends nothing


def test_a_free_prompt_reaches_both_models(router, stub, river):
    r = router("POST", "/api/chat-compare", json={"prompt": "say anything"})
    assert r.status_code == 200 and "say anything" in str(stub.requests[-1])


def test_errors_never_echo_a_key(router, stub, river, monkeypatch):
    stub.fail = (
        401,
        json.dumps(
            {"error": {"message": f"Incorrect API key provided: {SERVER_KEY}"}}
        ).encode(),
    )

    def leak(self):
        raise RuntimeError("auth failed for rk-secret-river-key-123")

    monkeypatch.setattr(train.RiverBackend, "_client", leak)
    r = router("POST", "/api/chat-compare", json={"preset": "broken-09"})
    errors = {e["side"]: e["message"] for e in events(r) if e.get("type") == "error"}
    assert errors["big"] == "OpenAI answered HTTP 401"
    assert (
        "rk-secret" not in r.text
        and SERVER_KEY not in r.text
        and "[key]" in errors["small"]
    )


def test_your_model_is_the_newest_graduated_river_checkpoint(workdir, monkeypatch):
    monkeypatch.delenv("CHAT_OWNED_MODEL", raising=False)
    assert chat_api.small_model() == chat_api.OLD_SMALL  # no registry.json yet
    tt = lambda state, model, at: {"state": state, "model": model, "graduated_at": at}
    (workdir / "registry.json").write_text(json.dumps({"task_types": {
        "a": tt("GRADUATED", "river://old/sampler_weights/a", "2026-09-27T10:00:00Z"),
        "b": tt("GRADUATED", "river://new/sampler_weights/b", "2026-09-27T12:00:00Z"),
        "c": tt("PROBATION", "river://newest/sampler_weights/c", "2026-09-27T13:00:00Z"),
        "d": tt("GRADUATED", "/local/checkpoint", "2026-09-27T14:00:00Z"),
    }}))
    assert chat_api.small_model() == "river://new/sampler_weights/b"
    monkeypatch.setenv("CHAT_OWNED_MODEL", "river://pinned/x")
    assert chat_api.small_model() == "river://pinned/x"


def test_the_preset_is_broken_state_09_with_its_real_failing_pytest(router):
    p = router("GET", "/api/chat-preset").json()
    src = next(f["text"] for f in p["files"] if f["path"] == "calc/mod_09.py")
    assert 'return " ".join(text.split())' in src and p["pytest"]["exit_code"] == 1
    assert "1 failed" in p["pytest"]["output"] and len(p["prompt"]) <= chat_api.MAX_PROMPT
    assert src in p["prompt"] and p["pytest"]["output"] in p["prompt"]


FIXED_09 = 'def reverse_words(text):\n    return " ".join(reversed(text.split()))\n'


def test_verify_runs_the_real_test_on_the_answer_s_code():
    ok = chat_api.verify("broken-09", f"Here:\n```python\n{FIXED_09}```\nIt reversed nothing before.")
    assert ok["exit_code"] == 0 and "1 passed" in ok["summary"]
    bad = chat_api.verify("broken-09", '```python\ndef reverse_words(text):\n    return " ".join(text.split())\n```')
    assert bad["exit_code"] == 1 and "failed" in bad["summary"]
    none = chat_api.verify("broken-09", "Just change the join.")
    assert none["exit_code"] is None and none["summary"] == "no complete fix returned"
    cut = chat_api.verify("broken-09", f"```python\n{FIXED_09}")  # cut off at the output cap: no closing fence
    assert cut["exit_code"] is None and cut["summary"] == "no complete fix returned"
    for evil in ("import os\nos.remove('x')", "open('tests/test_mod_09.py', 'w')", "x = 1  # see ../secrets.json"):
        refused = chat_api.verify("broken-09", f"```python\n{evil}\n```")
        assert refused["exit_code"] is None and "not run" in refused["summary"]


def test_a_preset_streams_one_verify_per_side_and_a_free_prompt_none(router, stub, river):
    ev = events(router("POST", "/api/chat-compare", json={"preset": "broken-09"}))
    verify = {e["side"]: e for e in ev if e.get("type") == "verify"}
    assert set(verify) == {"big", "small"} and all(v["exit_code"] is None for v in verify.values())  # stubs send no code
    assert ev[-1] == {"type": "end"}
    ev = events(router("POST", "/api/chat-compare", json={"prompt": "say anything"}))
    assert not [e for e in ev if e.get("type") == "verify"]


def test_end_to_end_the_stream_reports_the_real_pytest_result_per_side(router, stub, river, monkeypatch):
    """Through POST /api/chat-compare: the big model answers the right fix, your model a wrong one; each side's
    verify event is what pytest really printed after that side's code replaced calc/mod_09.py."""
    right = f"```python\n{FIXED_09}```\nIt joined the words without reversing them."
    wrong = '```python\ndef reverse_words(text):\n    return text\n```\nDone.'
    real = stub.chunks

    def chunks():  # the stub's own stream, with its "Fixed." text swapped for the right fix
        out = real()
        for c in out:
            for ch in c.get("choices") or []:
                d = ch.get("delta") or {}
                if d.get("content") == "Fi":
                    d["content"] = right
                elif d.get("content") == "xed.":
                    d["content"] = ""
        return out

    monkeypatch.setattr(stub, "chunks", chunks)
    body = json.dumps({"choices": [{"message": {"role": "assistant", "content": wrong}}], "usage": {"prompt_tokens": 12, "completion_tokens": 20}})
    monkeypatch.setattr(river, "chat_complete_from_checkpoint", lambda messages, **kw: SimpleNamespace(status_code=200, response_json=body))
    ev = events(router("POST", "/api/chat-compare", json={"preset": "broken-09"}))
    v = {e["side"]: e for e in ev if e.get("type") == "verify"}
    assert v["big"]["exit_code"] == 0 and "1 passed" in v["big"]["summary"]
    assert v["small"]["exit_code"] == 1 and "1 failed" in v["small"]["summary"]
    assert ev[-1] == {"type": "end"} and all(ev.index(v[s]) > next(i for i, e in enumerate(ev) if e.get("side") == s and e["type"] == "done") for s in v)


def test_thinking_level_comes_from_the_settings_the_calls_send(router, stub, river, monkeypatch):
    monkeypatch.delenv("OPENAI_EXTRA_BODY", raising=False)
    done = {e["side"]: e for e in events(router("POST", "/api/chat-compare", json={"preset": "broken-09"})) if e.get("type") == "done"}
    assert done["big"]["thinking"] == "none" and done["small"]["thinking"] == "off"
    assert stub.requests[-1][1]["reasoning_effort"] == "none" and river.calls[-1][2]["chat_template_kwargs"] == {"enable_thinking": False}
    monkeypatch.setenv("OPENAI_EXTRA_BODY", '{"service_tier": "priority", "reasoning_effort": "low"}')
    assert router("GET", "/api/thinking").json() == {"chat": {"big": "low (fast)", "small": "off"}, "agent": {"big": "low (fast)", "small": "off"}}
