"""`graduate bench` end to end on a scripted agent: a router per arm, the stub upstream, results.json, the cap."""

import json
import os
import socket
import subprocess
import sys
import time

import pytest

from conftest import ROOT, assert_shape, example, jsonl
from graduate import bench, runner

# Stands in for OpenCode: one streamed call to the router its config points at, then the fix.
AGENT = f"""#!{sys.executable}
import json, os, subprocess, time, urllib.error, urllib.request
url = json.loads(os.environ["OPENCODE_CONFIG_CONTENT"])["provider"]["graduate"]["options"]["baseURL"]
body = json.dumps({{"model": "graduate", "stream": True, "messages": [{{"role": "user", "content": "fix"}}]}})
req = urllib.request.Request(url + "/chat/completions", body.encode(), {{
    "authorization": "Bearer " + os.environ["GRADUATE_SESSION"], "content-type": "application/json"}})
for _ in range(int(os.environ.get("CALLS", 1))):  # a runaway agent keeps calling until the router is gone
    try:
        urllib.request.urlopen(req).read()
    except urllib.error.URLError:
        break
    time.sleep(0.2)
subprocess.run(["git", "checkout", "--", "calc"], check=True)
"""
STUB_CALL = {
    "input_tokens": 25000,
    "cached_input_tokens": 20000,
    "output_tokens": 40,
}  # scripts/stub-upstream.py


@pytest.fixture
def bench_env(workdir, monkeypatch):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    stub = subprocess.Popen(
        [sys.executable, ROOT / "scripts/stub-upstream.py", str(port), "auth.log"]
    )
    time.sleep(0.5)
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-stub")
    monkeypatch.setenv(
        "OPENCODE_CONFIG_CONTENT", "{}"
    )  # restored after bench points it at its router
    monkeypatch.setattr(runner, "ROUTER", runner.ROUTER)  # bench.main repoints it; monkeypatch undoes that
    agent = workdir / "agent"
    agent.write_text(AGENT)
    agent.chmod(0o755)
    monkeypatch.setattr(runner, "OPENCODE", str(agent))
    yield (
        lambda *args: (
            monkeypatch.setattr(sys, "argv", ["graduate bench", *args]) or bench.main()
        )
    )
    stub.kill()
    subprocess.run([ROOT / "scripts/reset-demo.sh", "clean"], check=True)


def per_run(model):
    return bench.cost({"model": model, **STUB_CALL}, "frontier")


def test_bench_runs_each_arm_on_its_own_model(bench_env, workdir):
    bench_env("--tasks", "01,07", "--yes")

    doc = json.loads((workdir / "bench/latest/results.json").read_text())
    want = example("fixtures/bench.example.json")
    assert_shape(doc, want)
    assert_shape(doc["budget"], want["budget"])
    for arm in ("frontier", "small", "owned"):
        assert_shape(doc["arms"][arm], want["arms"][arm])
    for s in doc["sessions"]:
        assert_shape(s, want["sessions"][0])
    frontier, small, owned = (doc["arms"][a] for a in ("frontier", "small", "owned"))
    assert (frontier["model"], small["model"]) == ("gpt-5.6-terra", "gpt-5.4-mini")
    assert (owned["model"], owned["note"], owned["runs"]) == (
        None,
        "n/a: nothing GRADUATED",
        0,
    )
    for a in (frontier, small):
        assert (a["runs"], a["passed"], a["turns"], a["output_tokens"]) == (2, 2, 1, 40)
        assert a["cost_usd"] == round(per_run(a["model"]), 6)
    assert (
        small["cost_usd"] < frontier["cost_usd"]
    )  # priced at its own rates, not the frontier's
    # Every call went through that arm's router to the upstream model of that arm.
    served = {m["session_id"]: m["model"] for m in jsonl("metrics.jsonl")}
    assert {
        (s["arm"], s["task"], served[s["session_id"]]) for s in doc["sessions"]
    } == {
        ("frontier", "01", "gpt-5.6-terra"),
        ("frontier", "07", "gpt-5.6-terra"),
        ("small", "01", "gpt-5.4-mini"),
        ("small", "07", "gpt-5.4-mini"),
    }
    assert doc["budget"]["spent_usd"] == round(
        2 * per_run("gpt-5.6-terra") + 2 * per_run("gpt-5.4-mini"), 6
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "demo-repo"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""


def test_bench_stops_at_the_cap(bench_env, workdir):
    # A past ledger row sets the estimate at $0.01 a run; each stub run really costs ~$0.0145.
    past = {
        "model": "gpt-5.6-terra",
        "routed_to": "frontier",
        "input_tokens": 5000,
        "cached_input_tokens": 0,
        "output_tokens": 0,
    }
    (workdir / "ledger.jsonl").write_text(json.dumps(past) + "\n")
    with pytest.raises(SystemExit) as e:
        bench_env(
            "--tasks", "01,02", "--arms", "frontier", "--max-usd", "0.02", "--yes"
        )
    assert e.value.code == 1
    doc = json.loads((workdir / "bench/latest/results.json").read_text())
    assert [s["task"] for s in doc["sessions"]] == ["01"]
    assert doc["arms"]["frontier"]["note"] == "CAP: stopped before frontier 02"
    assert doc["budget"]["spent_usd"] < 0.02


def test_watchdog_stops_the_router_mid_run(bench_env, workdir, monkeypatch):
    monkeypatch.setenv("CALLS", "40")
    past = {"model": "gpt-5.6-terra", "routed_to": "frontier", "input_tokens": 5000, "cached_input_tokens": 0, "output_tokens": 0}
    (workdir / "ledger.jsonl").write_text(json.dumps(past) + "\n")
    with pytest.raises(SystemExit):
        bench_env("--tasks", "01,02", "--arms", "frontier", "--max-usd", "0.05", "--yes")
    calls = len(jsonl("metrics.jsonl"))
    assert 4 <= calls < 20  # the cap is crossed on call 4; the router is gone within a second of it
    assert [s["task"] for s in json.loads((workdir / "bench/latest/results.json").read_text())["sessions"]] == ["01"]


def test_dry_run_and_refusal_spend_nothing(bench_env, workdir, capsys):
    bench_env("--dry-run")
    out = capsys.readouterr().out
    assert (
        "frontier(gpt-5.6-terra) small(gpt-5.4-mini) owned(n/a: nothing GRADUATED)"
        in out
    )
    assert "cap $1.00" in out
    with pytest.raises(SystemExit, match="refused"):
        bench_env("--max-usd", "0.01", "--yes")
    assert not (workdir / "bench").exists() and not os.path.exists("auth.log")
