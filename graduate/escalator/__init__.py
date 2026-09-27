"""Escalator: reset, rerun on frontier, demote (#23).

The runner (#34) calls three things:
  snapshot(repo)      before the agent starts: the pre-task working tree as a commit
  force_fail(row)     before the ledger append: GRADUATE_FORCE_FAIL=1 fails a graduated task type's attempt
  escalate(row, pre)  after a failed owned session that is not itself an escalation: returns the rerun's row

escalate saves the failed diff to sessions/<id>.diff, restores the repo to `pre` (nothing outside the repo is
touched), keeps a real failure as a negative example (contracts §6c), counts it against the task type and
demotes it to PROBATION at GRADUATE_FAIL_LIMIT, then reruns the task forced to the frontier with
escalated_from set. Self-check: python -m graduate.escalator
"""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from graduate import registry, trace
from graduate.registrar import dataset

FAIL_LIMIT = int(os.environ.get("GRADUATE_FAIL_LIMIT", "3"))
ISSUE = 23
DEAD_429 = ("per day", "insufficient_quota", "Request too large")


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=check
    ).stdout


def snapshot(repo):
    """`git stash create` keeps uncommitted edits (the demo's planted bug); a clean tree is just HEAD."""
    return (
        _git(repo, "stash", "create", check=False).strip()
        or _git(repo, "rev-parse", "HEAD", check=False).strip()
    )


def force_fail(row):
    """The demo's failure: owned serving (#37) isn't built, so a graduated task type's attempt is reported
    as a failed owned session, labelled forced_failure. Other task types are routed to the frontier: untouched."""
    if os.environ.get("GRADUATE_FORCE_FAIL") != "1" or row["escalated_from"]:
        return
    if row["routed_to"] == "owned" and row["exit_code"]:
        return  # a real failure needs no faking
    tt = registry.load()["task_types"].get(row["task_type"], {})
    if tt.get("state") == "GRADUATED":
        row.update(routed_to="owned", exit_code=1, forced_failure=True)


def _keep_negative(row):
    """Contracts §6c, available now; `dataset.build` (#21) rewrites the file from the ledger with the same record."""
    try:
        record = dataset.chat_record(row, negative=True)
    except (FileNotFoundError, IndexError):  # no session log
        return None
    path = dataset.DATA_DIR / f"{row['task_type']}.neg.jsonl"
    path.parent.mkdir(exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return path


def _dead_frontier():
    try:
        lines = Path(trace.TRACE_PATH).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("who") == "Router → OpenAI":
            r = e["result"]
            dead = r.startswith("401") or (r.startswith("429") and any(s in r for s in DEAD_429))
            ts = datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return r if dead and datetime.now(timezone.utc) - ts < timedelta(hours=1) else None
    return None


def escalate(row, pre):
    from graduate import runner  # the runner imports this module

    sid, repo, task_type = row["session_id"], row["repo"], row["task_type"]
    how = (
        "was marked failed for the demo (GRADUATE_FORCE_FAIL=1)"
        if row["forced_failure"]
        else f"failed its tests (exit {row['exit_code']})"
    )

    diff = Path("sessions") / f"{sid}.diff"
    diff.parent.mkdir(exist_ok=True)
    diff.write_text(_git(repo, "diff", pre, "--", "."))
    # The `.` pathspec keeps both inside the repo; ignored files (.venv) stay.
    _git(repo, "restore", f"--source={pre}", "--worktree", "--", ".")
    _git(repo, "clean", "-fdq", "--", ".")
    trace.emit(
        "Escalator → repo",
        f"git diff > {diff} && git restore --source={pre[:7]} -- . && git clean -fd -- .",
        f"attempt {how} · diff saved · {repo} back to its pre-task state",
        ISSUE,
        ["ledger", "escalator"],
        ["failed"],
        sid,
    )

    kept = None if row["forced_failure"] else _keep_negative(row)
    tt = registry.load()["task_types"].get(task_type)
    fails = (tt["failures_since_graduation"] + 1) if tt else 1
    if tt:
        registry.update(task_type, failures_since_graduation=fails)
    registry.add_event(
        "failed",
        task_type,
        f"{task_type}: your model's attempt {how}, failure {fails} of {FAIL_LIMIT}. "
        f"Saved the diff to {diff}, reset {repo}, "
        + (
            f"kept it as a negative example in {kept}."
            if kept
            else "not kept as a negative example."
        ),
    )
    if tt and tt["state"] == "GRADUATED" and fails >= FAIL_LIMIT:
        registry.transition(task_type, "PROBATION")
        registry.add_event(
            "probation",
            task_type,
            f"{task_type} failed {fails} times since graduation. Moved to probation: "
            "requests go to the frontier until it is retrained.",
        )

    dead = _dead_frontier()
    if dead:
        why = f"no frontier rerun of {sid}: the frontier's last answer was {dead[:220]}"
        trace.emit("Escalator → Runner", "graduate run --force-frontier", why, ISSUE,
                   ["escalator", "router", "openai"], ["rerun", "frontier"], sid)
        print(why)
        return row
    trace.emit(
        "Escalator → Runner",
        "graduate run --force-frontier",
        f"rerun of {sid} on the frontier, escalated_from={sid}",
        ISSUE,
        ["escalator", "router", "openai"],
        ["rerun", "frontier"],
        sid,
    )
    rerun = runner.run(
        row["prompt"],
        row["verify_command"],
        repo,
        force_frontier=True,
        escalated_from=sid,
        task_type=task_type,
        harness=row.get("harness", "opencode"),
    )
    ok = rerun["exit_code"] == 0
    registry.add_event(
        "escalated",
        task_type,
        f"{task_type}: reran the task on the frontier as {rerun['session_id']}: "
        + (
            "tests pass."
            if ok
            else f"still failing (exit {rerun['exit_code']}), not escalated again."
        ),
    )
    print(
        f"{sid} owned_then_frontier → {rerun['session_id']} exit {rerun['exit_code']}"
    )
    return rerun
