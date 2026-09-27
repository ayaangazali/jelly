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
