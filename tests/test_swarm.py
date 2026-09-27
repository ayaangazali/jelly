"""graduate swarm (#8): fan-out, the run record's transitions, and isolation, with a fake runner (no OpenCode)."""

import hashlib
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from graduate import runner, swarm, trace
from conftest import jsonl


def _demo_hash():
    files = sorted(p for p in swarm.DEMO.rglob("*") if p.is_file() and ".pytest_cache" not in p.parts)
    return hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()


def test_agents_run_at_once_each_in_its_own_copy(workdir, monkeypatch):
    before = _demo_hash()
    together = threading.Barrier(4, timeout=10)  # breaks unless all 4 agents are inside run() at the same time
    seen = {}

    def fake_run(prompt, verify, repo, timeout, task_type, session_id):
        n = verify.split("test_mod_")[1][:2]
        me = next(a for a in json.loads(Path("swarm/latest.json").read_text())["agents"] if a["task"] == n)
        assert (me["status"], me["session_id"], me["task_type"]) == ("running", session_id, "fix-failing-test")
        diff = subprocess.run(["git", "-C", repo, "diff", "--name-only"], capture_output=True, text=True).stdout
        assert diff == f"calc/mod_{n}.py\n"  # its own git repo at demo-repo's HEAD, broken state planted
        Path(repo, f"calc/mod_{n}.py").write_text("# the agent's edit\n")
        if n == "02":
            trace.emit("Runner → GBrain", "a2a get", "note", 0, ["runner", "gbrain"], ["a2a-read"], session_id)
        seen[n] = repo
        together.wait()
        return {"session_id": session_id, "exit_code": 1 if n == "04" else 0, "turns": 3}

    monkeypatch.setattr(runner, "run", fake_run)
    record = swarm.swarm(["01", "02", "03", "04"], 4)

    assert [(a["agent"], a["task"], a["status"], a["exit_code"], a["turns"], a["a2a_read"], a["a2a_write"]) for a in record["agents"]] == [
        ("a1", "01", "passed", 0, 3, False, False),
        ("a2", "02", "passed", 0, 3, True, False),
        ("a3", "03", "passed", 0, 3, False, False),
        ("a4", "04", "failed", 1, 3, False, False),
    ]
    assert json.loads(Path(f"swarm/{record['swarm_id']}.json").read_text()) == record
    assert json.loads(Path("swarm/latest.json").read_text()) == record
    assert len(set(seen.values())) == 4 and not any(Path(r).exists() for r in seen.values())  # temp copies cleaned
    fanout = [e for e in jsonl("trace.jsonl") if e["edges"] == ["fanout"]]
    assert {(e["who"], tuple(e["nodes"]), e["session_id"]) for e in fanout} == {
        ("Swarm → Runner", ("swarm", "runner"), a["session_id"]) for a in record["agents"]
    }
    assert len({a["session_id"] for a in record["agents"]}) == 4
    assert _demo_hash() == before  # the checkout's demo-repo is untouched


def test_extra_agents_round_robin_and_the_rest_wait_queued(workdir, monkeypatch):
    queued = []

    def fake_run(prompt, verify, repo, timeout, task_type, session_id):
        queued.append([a["status"] for a in json.loads(Path("swarm/latest.json").read_text())["agents"]])
        return {"session_id": session_id, "exit_code": 0, "turns": 1}

    monkeypatch.setattr(runner, "run", fake_run)
    swarm.swarm(["01", "02"], 1)
    assert queued[0] == ["running", "queued"]  # one at a time: the second agent waits
    assert [a["task"] for a in swarm.swarm(["01", "02"], 3)["agents"]] == ["01", "02", "01"]


def test_superset_launcher_says_why_it_cannot_run(workdir, monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(sys, "argv", ["graduate swarm", "--tasks", "01", "--launcher", "superset"])
    with pytest.raises(SystemExit, match="Superset CLI is not installed here. Use --launcher local"):
        swarm.main()


@pytest.mark.parametrize("agents", ["0", "9"])
def test_agents_are_capped_at_8_without_force(workdir, monkeypatch, agents):
    monkeypatch.setattr(sys, "argv", ["graduate swarm", "--tasks", "01", "--agents", agents])
    with pytest.raises(SystemExit, match="1-8 at once"):
        swarm.main()
