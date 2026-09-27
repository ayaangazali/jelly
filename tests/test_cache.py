"""Verified-response cache (#144) against the stub frontier: what replays, what never does, what gets evicted."""

import json
import uuid

import pytest

from conftest import example, jsonl
from graduate import registry, runner
from graduate.router import cache, metrics

SYSTEM = "You are opencode.\n<env>\n  Working directory: {}\n  Today's date: {}\n</env>"


@pytest.fixture(autouse=True)
def fresh_index(monkeypatch):
    monkeypatch.setattr(cache, "_index", {"mtime": None, "keys": {}, "evicted": set()})


def new_sid():
    return "sess-" + uuid.uuid4().hex[:12]


def body(root="/work/a/demo-repo", date="Sun Sep 27 2026", read="def add(a, b):\n    return a - b\n", **extra):
    """An OpenCode-like turn: system prompt with its cwd and date, the task, then one file read under the cwd."""
    return {
        "model": "graduate",
        "messages": [
            {"role": "system", "content": SYSTEM.format(root, date)},
            {"role": "user", "content": "The test tests/test_mod_01.py is failing."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "read", "arguments": json.dumps({"filePath": f"{root}/calc/mod_01.py"})}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": f"{root}/calc/mod_01.py\n{read}"},
        ],
        "tools": [{"type": "function", "function": {"name": "read", "parameters": {}}}],
        **extra,
    }


def post(router, sid, b):
    return router("POST", "/v1/chat/completions", headers={"Authorization": f"Bearer {sid}"}, json=b)


def verified(router, b, **row):
    """A frontier session that answered `b`, on the ledger as a clean verified run unless `row` says otherwise."""
    sid = new_sid()
    assert post(router, sid, b).status_code == 200
    ledger_row = example("fixtures/ledger.example.jsonl") | {"session_id": sid} | row
    with open("ledger.jsonl", "a") as f:
        f.write(json.dumps(ledger_row) + "\n")
    return sid


@pytest.mark.parametrize("stream", [False, True])
def test_a_verified_turn_replays_at_zero_cost_without_the_frontier(router, stub, workdir, stream):
    stub.tools = True
    src = verified(router, body(stream=stream))
    calls = len(stub.requests)
    sid = new_sid()
    r = post(router, sid, body(stream=stream))
    assert r.status_code == 200 and len(stub.requests) == calls  # no model call
    got = jsonl(workdir / f"sessions/{sid}.jsonl")[0]
    assert (got["upstream"], got["model"]) == ("cache", f"cache:{src}")
    assert got["response"] == stub.message()  # the recorded answer, streamed or not
    rec = jsonl(workdir / "metrics.jsonl")[-1]
    assert rec["upstream"] == "cache" and rec["cost_usd"] == 0
    assert rec["saved_usd"] == metrics.cost(got["usage"], "frontier") > 0
    s = router("GET", "/api/cache").json()
    assert (s["hits"], s["turns"], s["hit_rate"], s["saved_usd"], s["entries"]) == (1, 2, 0.5, rec["saved_usd"], 1)
    hit = [e for e in jsonl(workdir / "trace.jsonl") if e["who"] == "Router → Cache"]
    assert [e["result"].split(" · ")[:2] for e in hit] == [["hit", src]]


def test_the_cwd_and_date_are_normalized_and_paths_map_back(router, stub, workdir):
    """OpenCode's prompt carries the absolute cwd and the date: without normalizing both a rerun never hits."""
    stub.tools = True
    stub.message = lambda: {"role": "assistant", "content": "", "finish_reason": "tool_calls", "tool_calls": [
        {"id": "call_9", "type": "function", "function": {"name": "edit", "arguments": json.dumps({"filePath": "/work/a/demo-repo/calc/mod_01.py"})}}]}
    stub.tools = False  # the non-stream body is built from message()
    verified(router, body())
    calls, sid = len(stub.requests), new_sid()
    post(router, sid, body(root="/work/b/demo-repo", date="Mon Sep 28 2026"))
    assert len(stub.requests) == calls
    [call] = jsonl(workdir / f"sessions/{sid}.jsonl")[0]["response"]["tool_calls"]
    assert json.loads(call["function"]["arguments"]) == {"filePath": "/work/b/demo-repo/calc/mod_01.py"}


@pytest.mark.parametrize("change", [
    {"read": "def add(a, b):\n    return a * b\n"},  # the file read diverges: stale state
    {"tools": []},  # another harness's tools
])
def test_a_different_prefix_misses_and_falls_through(router, stub, workdir, change):
    verified(router, body())
    calls, sid = len(stub.requests), new_sid()
    b = body(**{k: v for k, v in change.items() if k == "read"})
    if "tools" in change:
        b["tools"] = change["tools"]
    assert post(router, sid, b).status_code == 200
    assert len(stub.requests) == calls + 1
    assert jsonl(workdir / f"sessions/{sid}.jsonl")[0]["upstream"] == "frontier"
    assert [e["result"].split(" · ")[0] for e in jsonl(workdir / "trace.jsonl") if e["who"] == "Router → Cache"] == ["miss"]


@pytest.mark.parametrize("row", [
    {"tampered": True},
    {"forced_failure": True},
    {"routed_to": "owned"},
    {"routed_to": "mixed"},
    {"routed_to": "cache"},
    {"escalated_from": "sess-000000000000"},
    {"exit_code": 1},
])
def test_only_clean_verified_frontier_sessions_are_cached(router, stub, row):
    verified(router, body(), **row)
    calls = len(stub.requests)
    post(router, new_sid(), body())
    assert len(stub.requests) == calls + 1


def test_forced_frontier_and_anonymous_sessions_bypass_the_cache(router, stub):
    verified(router, body())
    calls, sid = len(stub.requests), new_sid()
    router("POST", "/api/sessions", json={"session_id": sid, "force_frontier": True})  # an escalation rerun
    post(router, sid, body())
    post(router, "not-a-session", body())
    assert len(stub.requests) == calls + 2


def test_corrupt_or_missing_files_fail_open(router, stub, workdir):
    src = verified(router, body())
    log = workdir / f"sessions/{src}.jsonl"
    log.write_text(log.read_text() + '{"truncated": ')  # #125
    with open("ledger.jsonl", "a") as f:
        f.write('{"session_id": "sess-111111111111", "routed_to": "frontier", "exit_code": 0, "tampered": false, '
                '"forced_failure": false, "escalated_from": null}\n{"half a row')  # no session log, then garbage
    calls = len(stub.requests)
    post(router, new_sid(), body())
    assert len(stub.requests) == calls  # the good line still replays
    log.write_text("not json\n")
    (workdir / "ledger.jsonl").write_text((workdir / "ledger.jsonl").read_text() + "\n")  # new mtime: rebuild
    assert post(router, new_sid(), body()).status_code == 200 and len(stub.requests) == calls + 1


def test_a_failed_cache_session_is_evicted_and_escalated(router, stub, workdir, monkeypatch):
    """The runner labels it `cache`, the escalator reruns it on the frontier without counting it against the
    model, and the router never serves those keys again, even from the verified session that recorded them."""
    verified(router, body())
    sid = new_sid()
    post(router, sid, body())  # served from cache

    served = jsonl(workdir / f"sessions/{sid}.jsonl")
    monkeypatch.setattr(runner, "_router", lambda m, path, **kw: served if path.endswith("/log") else {"task_type": "fix-failing-test", "turns": 1})
    monkeypatch.setattr(runner, "OPENCODE", "true")
    reruns = []
    monkeypatch.setattr(runner.escalator, "_git", lambda *a, **kw: "")
    real_run = runner.run
    monkeypatch.setattr(runner, "run", lambda *a, **kw: reruns.append(kw) or {"session_id": "sess-rerun", "exit_code": 0})
    row = real_run("Fix calc.", "false", str(workdir), session_id=sid)

    assert (row["session_id"], reruns[0]["escalated_from"], reruns[0]["force_frontier"]) == ("sess-rerun", sid, True)
    [failed] = [r for r in jsonl("ledger.jsonl") if r["session_id"] == sid]
    assert (failed["routed_to"], failed["exit_code"]) == ("cache", 1)
    assert not (workdir / "data").exists()  # no negative example
    [failed_event] = [e["text"] for e in registry.load()["events"] if e["kind"] == "failed"]
    assert "served from the verified cache" in failed_event and "failure" not in failed_event  # not the model's

    calls = len(stub.requests)
    post(router, new_sid(), body())
    assert len(stub.requests) == calls + 1
    assert any(e["result"].endswith("entry evicted") for e in jsonl("trace.jsonl") if e["who"] == "Router → Cache")
