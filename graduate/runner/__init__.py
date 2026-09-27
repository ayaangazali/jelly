"""`graduate run`: one task, one session (#34).

graduate run --task-file demo-repo/tasks/01.json --repo demo-repo [--force-frontier] [--timeout 600]

Launches `opencode run <prompt>` in the repo with GRADUATE_SESSION set (the router
reads it as the bearer), streams its output to trace.terminal, runs the task's verify
command in the repo, and appends one ledger row (contracts §2).
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from graduate import a2a, escalator, ledger, memorable, trace
from graduate.reward import parse_pytest_summary

ROUTER = os.environ.get("GRADUATE_ROUTER", "http://localhost:4141")
OPENCODE = os.environ.get("OPENCODE_BIN", str(Path.home() / ".opencode/bin/opencode"))
ISSUE = 34


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _router(method, path, **kw):
    """Fail open: the router being down or missing an endpoint never stops a run."""
    try:
        r = httpx.request(method, ROUTER + path, timeout=5, **kw)
        return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def _session_totals(session_id):
    """Counts and cost from the router aggregate (#17); upstream and model from the session log (#35)."""
    out = _router("GET", f"/api/sessions/{session_id}") or {}
    calls = _router("GET", f"/api/sessions/{session_id}/log") or []
    if calls:
        out["upstream"], out["model"] = calls[-1]["upstream"], calls[-1]["model"]
        if any(c["upstream"] == "cache" for c in calls):  # #144: never a verified frontier run or training data
            out["upstream"] = "cache"
    return out


def _tree(repo):
    with tempfile.TemporaryDirectory() as d:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(d, "index")}
        subprocess.run(["git", "add", "-A", "."], cwd=repo, env=env, capture_output=True)
        return subprocess.run(["git", "write-tree"], cwd=repo, env=env, capture_output=True, text=True).stdout.strip()


def _tests_changed(repo, before):
    out = subprocess.run(
        ["git", "diff-tree", "-r", "-z", "--name-only", "--no-renames", before, _tree(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
    ).stdout
    parts = [Path(p).parts for p in out.split("\0") if p]
    return any(("tests" in d[:-1] or d[-1] == "conftest.py") and "__pycache__" not in d for d in parts)


def run(prompt, verify, repo, force_frontier=False, timeout=600, escalated_from=None, task_type=None, session_id=None):
    session_id = session_id or "sess-" + uuid.uuid4().hex[:12]  # graduate swarm picks it to trace the fan-out first
    start_commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    ).stdout.strip()
    pre_task = escalator.snapshot(repo)  # #23 resets to this
    before = _tree(repo)
    _router(
        "POST",
        "/api/sessions",
        json={
            "session_id": session_id,
            "prompt": prompt,
            "repo": repo,
            "verify": verify,
            "force_frontier": force_frontier,
            "task_type": task_type,
        },
    )

    note = task_type and a2a.get(task_type, session_id)
    sent = f"## Notes from other agents\n{note}\n\n{prompt}" if note else prompt
    started_at, t0 = _now(), time.monotonic()
    trace.emit(
        "Runner → OpenCode",
        f'opencode run "{sent}"',
        f"env GRADUATE_SESSION={session_id}",
        ISSUE,
        ["runner", "opencode"],
        ["launch"],
        session_id,
    )
    # OpenCode takes its project dir from $PWD, not the process cwd.
    env = {**os.environ, "GRADUATE_SESSION": session_id, "PWD": os.path.abspath(repo)}
    env.pop("OPENAI_API_KEY", None)  # only the router holds it, as in demo.sh (#97)
    proc = subprocess.Popen(
        [OPENCODE, "run", sent],
        cwd=repo,
        text=True,
        start_new_session=True,
        env=env,
        stdin=subprocess.DEVNULL,  # `opencode run` reads a piped stdin into the prompt and waits for EOF
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    timed_out = []

    def kill():  # the whole process group: OpenCode's children keep the pipe open otherwise
        timed_out.append(True)
        os.killpg(proc.pid, signal.SIGKILL)

    timer = threading.Timer(timeout, kill)
    timer.start()
    for line in proc.stdout:
        print(line, end="", flush=True)
        trace.terminal(f"[{session_id}] {line}")
    proc.wait()
    timer.cancel()

    tampered = _tests_changed(repo, before)
    for p in [*Path(repo).rglob("__pycache__"), Path(repo, ".pytest_cache")]:
        if ".venv" not in p.parts:
            shutil.rmtree(p, ignore_errors=True)
    # Always verify, even after a crash or timeout, and only inside the task repo.
    v = subprocess.run(verify, shell=True, cwd=repo, capture_output=True, text=True)
    passed, total = parse_pytest_summary(v.stdout)
    summary_ok = (total and passed == total) or not re.search(r"\bpytest\b", verify)
    verified = v.returncode == 0 and summary_ok and not tampered
    exit_code = 124 if timed_out else v.returncode or (0 if verified else 1)
    for line in (v.stdout + v.stderr).splitlines():
        trace.terminal(f"[{session_id}] {line}")
    trace.emit(
        "Runner → Test suite",
        verify,
        f"exit {exit_code} · {passed} passed",
        ISSUE,
        ["runner", "pytest"],
        ["verify"],
        session_id,
    )

    totals = _session_totals(session_id)
    routed_to = totals.get("upstream", "frontier")
    row = {
        "session_id": session_id,
        "task_type": totals.get("task_type", "unknown"),
        "procedure_slug": None,
        "prompt": prompt,
        "repo": repo,
        "start_commit": start_commit,
        "verify_command": verify,
        "exit_code": exit_code,
        "tests_passed": passed if total else None,
        "tests_total": total or None,
        "routed_to": routed_to,
        "model": totals.get("model", "unknown"),
        "turns": totals.get("turns", 0),
        "tool_calls": totals.get("tool_calls", 0),
        "input_tokens": totals.get("input_tokens", 0),
        "cached_input_tokens": totals.get("cached_input_tokens", 0),
        "output_tokens": totals.get("output_tokens", 0),
        "cost_usd": totals.get("cost_usd", 0.0),
        "wall_secs": round(time.monotonic() - t0, 1),
        "started_at": started_at,
        "ended_at": _now(),
        "escalated_from": escalated_from,
        "forced_failure": False,
        "tampered": tampered,
    }
    if routed_to == "frontier" and exit_code == 0:
        row["procedure_slug"] = memorable.ingest(session_id, row["task_type"], verify, exit_code)
    escalator.force_fail(row)  # #23: GRADUATE_FORCE_FAIL=1
    if task_type and row["exit_code"] == 0:  # verified, and not forced to fail
        diff = ["git", "diff-tree", "-r", "--name-only", before, _tree(repo)]
        files = [f for f in subprocess.run(diff, cwd=repo, capture_output=True, text=True).stdout.split() if "__pycache__" not in f]
        a2a.put(task_type, f"{session_id} passed: changed {', '.join(files) or 'nothing'}; `{verify}` went green.", session_id)
    ledger.append(row)
    trace.emit(
        "Runner → Ledger",
        "append ledger.jsonl",
        json.dumps(row),
        ISSUE,
        ["runner", "ledger"],
        ["exit"],
        session_id,
    )

    print(
        f"{session_id} {row['routed_to']} exit {row['exit_code']} · {passed}/{total} passed · "
        f"{row['turns']} turns · ${row['cost_usd']} · {row['wall_secs']}s"
    )
    if row["routed_to"] in ("owned", "cache") and row["exit_code"] != 0 and not escalated_from:
        try:  # #23; never escalate an escalation
            return escalator.escalate(row, pre_task)
        except Exception as e:  # fail open: the failed row is already on the ledger
            print(f"escalation failed: {e!r}")
    return row


def main():
    p = argparse.ArgumentParser(prog="graduate run")
    p.add_argument("--task-file", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--force-frontier", action="store_true")
    p.add_argument("--timeout", type=float, default=600)
    a = p.parse_args()
    # #83: say what to do instead of a traceback, or OpenCode hanging on a dead router until --timeout
    if not Path(a.task_file).is_file():
        sys.exit(f"no task file {a.task_file}: run from the jelly checkout, where demo-repo/tasks/ lives")
    if not shutil.which(OPENCODE):
        sys.exit(f"OpenCode not found at {OPENCODE}: curl -fsSL https://opencode.ai/install | bash, or set OPENCODE_BIN")
    if _router("GET", "/state") is None:
        sys.exit(f"no router at {ROUTER}: start `graduate up` in another terminal first")
    task = json.loads(Path(a.task_file).read_text())
    row = run(task["prompt"], task["verify"], a.repo, a.force_frontier, a.timeout, task_type=task.get("task_type"))
    raise SystemExit(row["exit_code"])
