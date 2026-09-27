"""Self-check: python -m graduate.escalator

Runs the real runner end to end in a scratch git repo, with a fake OpenCode that fixes the planted bug and no
router (the runner fails open to frontier). Covers: forced failure -> two linked rows and a passing repo, the
reset restoring the planted bug but nothing outside the repo, PROBATION on the third failure and frontier right
after, and a real owned failure kept as a negative example that is not escalated twice.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from graduate import ledger, registry, runner

AGENT = """#!{python}
import json, os, pathlib
seen = {{"m": pathlib.Path("m.py").read_text(), "scratch": pathlib.Path("scratch.txt").exists()}}
open(os.environ["SEEN"], "a").write(json.dumps(seen) + "\\n")
pathlib.Path("m.py").write_text(os.environ.get("FIX", "def f():\\n    return 2\\n"))
pathlib.Path("scratch.txt").write_text("agent scratch file")
sid = os.environ["GRADUATE_SESSION"]
call = {{"session_id": sid, "upstream": "owned", "request": {{"messages": [{{"role": "user", "content": "fix m"}}],
        "tools": [{{"type": "function", "function": {{"name": "edit", "description": "Edit", "parameters": {{}}}}}}]}},
        "response": {{"role": "assistant", "content": "Done.", "tool_calls": None, "finish_reason": "stop"}}}}
open(os.path.join(os.environ["SESSIONS"], sid + ".jsonl"), "a").write(json.dumps(call) + "\\n")
"""
BROKEN = "def f():\n    return 1\n"


def sh(*cmd, cwd="."):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


def graduated(task_type):
    reg = registry.load()
    reg["task_types"][task_type] = {
        **registry._new_task_type(task_type),
        "state": "GRADUATED",
    }
    registry._write(reg)


def run():
    Path("repo/m.py").write_text(BROKEN)  # the planted, uncommitted bug
    return runner.run(
        "fix m", f"{sys.executable} -B -c 'import m; assert m.f() == 2'", "repo"
    )


def seen():
    return [json.loads(line) for line in open("seen.jsonl")]


def check():
    os.chdir(tempfile.mkdtemp())
    os.makedirs("repo")
    Path("repo/m.py").write_text("def f():\n    return 2\n")
    sh("git", "init", "-q")
    sh("git", "add", ".")
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    Path("outside.txt").write_text("untracked, outside the task repo")
    os.makedirs("sessions")
    Path("agent").write_text(AGENT.format(python=sys.executable))
    os.chmod("agent", 0o755)
    runner.OPENCODE, runner.ROUTER = os.path.abspath("agent"), "http://127.0.0.1:9"
    os.environ.update(
        SEEN=os.path.abspath("seen.jsonl"),
        SESSIONS=os.path.abspath("sessions"),
        MEMORABLE_BIN="false",
    )
    os.environ["GRADUATE_FORCE_FAIL"] = "1"
    graduated("unknown")  # no router: the runner's task type is `unknown`

    # Forced failures 1-3: failed row + linked passing rerun; the rerun starts from the planted bug again.
    for n in (1, 2, 3):
        final = run()
        failed, rerun = ledger.rows()[-2:]
        assert final == rerun and rerun["exit_code"] == 0, rerun
        assert (failed["routed_to"], failed["exit_code"], failed["forced_failure"]) == (
            "owned",
            1,
            True,
        )
        assert (
            rerun["routed_to"],
            rerun["escalated_from"],
            rerun["forced_failure"],
        ) == (
            "frontier",
            failed["session_id"],
            False,
        )
        assert seen()[-1] == {"m": BROKEN, "scratch": False}, seen()[-1]
        assert (
            "-    return 1" in Path(f"sessions/{failed['session_id']}.diff").read_text()
        )
        tt = registry.load()["task_types"]["unknown"]
        assert tt["failures_since_graduation"] == n
        assert tt["state"] == ("PROBATION" if n == 3 else "GRADUATED"), tt["state"]
    assert (
        Path("outside.txt").exists() and not Path("data/unknown.neg.jsonl").exists()
    )  # forced: no negative example

    # Fourth forced run: on probation, so it is a plain frontier session.
    row = run()
    assert (row["routed_to"], row["exit_code"], row["forced_failure"]) == (
        "frontier",
        0,
        False,
    ), row
    assert len(ledger.rows()) == 7

    kinds = [e["kind"] for e in registry.load()["events"]]
    assert kinds[:4] == ["escalated", "probation", "failed", "escalated"], kinds
    assert all(
        "marked failed for the demo" in e["text"]
        for e in registry.load()["events"]
        if e["kind"] == "failed"
    )
    edges = {
        e
        for line in open("trace.jsonl")
        for e in json.loads(line)["edges"]
        if json.loads(line)["issue"] == 23
    }
    assert edges == {"failed", "rerun", "frontier"}, edges

    # A real owned failure: kept as a negative, and its failing rerun is not escalated again.
    graduated("t2")
    runner._session_totals = lambda sid: {"upstream": "owned", "task_type": "t2"}
    os.environ["FIX"] = "def f():\n    return 3\n"
    final = run()
    failed, rerun = ledger.rows()[-2:]
    assert (
        len(ledger.rows()) == 9
        and final == rerun
        and rerun["escalated_from"] == failed["session_id"]
    )
    assert (failed["exit_code"], failed["forced_failure"], rerun["exit_code"]) == (
        1,
        False,
        1,
    )
    (neg,) = [json.loads(line) for line in open("data/t2.neg.jsonl")]
    assert (
        neg["metadata"]["negative"]
        and neg["metadata"]["session_id"] == failed["session_id"]
    )
    assert neg["messages"][-1] == {"role": "assistant", "content": "Done.", "tool_calls": None}, neg[
        "messages"
    ][-1]
    assert neg["tools"] == [{"name": "edit", "description": "Edit", "parameters": {}}]
    print(
        "escalator self-check ok: 3 forced failures -> linked reruns -> PROBATION, reset stays in the repo, negatives kept"
    )


if __name__ == "__main__":
    check()
