"""Ledger watcher: counts verified runs, flips READY (#19). Shape: graduate/contracts.md §1, §2, §5.

python -m graduate.watcher           tail ledger.jsonl, rescan whenever it changes
python -m graduate.watcher --once    replay the whole ledger once and exit
python -m graduate.watcher --check   self-check
"""

import calendar
import json
import os
import subprocess
import time

from graduate import registry, trace

LEDGER_PATH = "ledger.jsonl"
POLL_SECS = 1.0
NUMBERS = ("turns", "tool_calls", "cost_usd", "wall_secs")
STOPPED = "Training stopped without finishing (exit unknown). Approve again to retry."


def _rows():
    """Decoded rows and how many lines did not decode (a runner killed mid-append, #132)."""
    # Read the file directly: the row shape is the contract, ledger.py (#34) is the writer.
    try:
        with open(LEDGER_PATH, encoding="utf-8") as f:
            lines = f.read().split("\n")[:-1]  # drop a half-written last line
    except FileNotFoundError:
        return [], 0
    rows, bad = [], 0
    for line in filter(str.strip, lines):
        try:
            rows.append(json.loads(line))
        except ValueError:
            bad += 1
    return rows, bad


def _avg(rows):
    return {k: sum(r[k] for r in rows) / len(rows) for k in NUMBERS} if rows else None


def scan():
    """Recompute every task type from the whole ledger. Same ledger in, same registry out."""
    # ponytail: full re-read per change; keep a byte offset if the ledger outgrows a demo day.
    rows, bad = _rows()
    by_type = {}
    for r in rows:
        if r["task_type"] != "unknown":
            by_type.setdefault(r["task_type"], []).append(r)
    trace.emit(
        "Ledger → Watcher",
        f"tail {LEDGER_PATH}",
        f"{len(rows)} rows, {len(by_type)} task types"
        + (f", {bad} unreadable lines skipped" if bad else ""),
        19,
        ["ledger", "watcher"],
        ["tail"],
    )
    known = registry.load()["task_types"]
    for t, rs in by_type.items():
        frontier = [r for r in rs if r["routed_to"] == "frontier"]
        verified = [
            r for r in frontier if r["exit_code"] == 0 and r["escalated_from"] is None
        ]
        since = known.get(t, {}).get("graduated_at") or ""
        owned = [
            r
            for r in rs
            if r["routed_to"] == "owned"
            and r["exit_code"] == 0
            and r["started_at"] >= since
        ]
        fields = {
            "verified_runs": len(verified),
            "failed_runs": sum(r["exit_code"] != 0 for r in frontier),
            "baseline": _avg(verified),
            "verified_since_graduation": len(owned),
            "current": _avg(owned),
        }
        slugs = [r["procedure_slug"] for r in rs if r["procedure_slug"]]
        if slugs:
            fields["procedure_slug"] = slugs[-1]
        # New types start as the bare slug with no verify command (#76): name them from the slug and the ledger.
        # The command is what every run's command starts with; one that still covers every run (hand-set) stays.
        old = known.get(t, {})
        cmds = sorted({r["verify_command"] for r in rs if r.get("verify_command")})
        if cmds:
            common = os.path.commonprefix(cmds)
            cmd = common if len(cmds) == 1 else common.rsplit(" ", 1)[0]
            have = old.get("verify_command")
            if not have or not all(c.startswith(have) for c in cmds):
                fields["verify_command"] = cmd
        if old.get("title", t) == t:
            fields["title"] = t.replace("-", " ").capitalize()
        n = len(verified)
        if (
            registry.update(t, **fields)["state"] == "LEARNING"
            and n >= registry.GRADUATE_N
        ):
            registry.transition(t, "READY")
            registry.add_event(
                "ready",
                t,
                f"{t} has {n} verified runs. Waiting for you to approve the training data.",
            )
            trace.emit(
                "Watcher → registry.json",
                f'verified_runs("{t}") = {n}   (bar: {registry.GRADUATE_N})',
                "state READY · consent not given yet → ask you",
                19,
                ["ledger", "watcher", "registry"],
                ["tail", "ready"],
            )
    return by_type


def started(pid):
    """Start time (epoch s) of a live process; None once it is gone or a zombie. `ps` so macOS works too."""
    ps = ["ps", "-o", "stat=,lstart=", "-p", str(pid)]
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC"}
    out = subprocess.run(ps, capture_output=True, text=True, env=env).stdout.split(
        None, 1
    )
    if not out or out[0].startswith("Z"):
        return None
    return calendar.timegm(time.strptime(out[1].strip(), "%a %b %d %H:%M:%S %Y"))


def _alive(rec):
    try:
        now = rec["started"] and started(rec["pid"])
    except (IndexError, ValueError):
        return True
    return bool(now) and abs(now - rec["started"]) <= 2


def reap():
    """A trainer the OS killed (OOM, SIGKILL, sleep) leaves TRAINING behind (#116): back to READY so the user can retry.
    The consent endpoint records the trainer's pid and start time; another start time is a reused pid."""
    for t, tt in registry.load()["task_types"].items():
        rec = tt.get("trainer")
        if tt["state"] != "TRAINING" or not rec or _alive(rec):
            continue
        try:
            registry.transition(t, "READY")
        except registry.IllegalTransition:
            continue
        registry.add_event("training", t, STOPPED)


def _mtime():
    try:
        return os.stat(LEDGER_PATH).st_mtime_ns
    except FileNotFoundError:
        return None


def watch():
    seen = None
    while True:
        if (m := _mtime()) != seen:
            seen = m
            try:
                scan()
            except Exception as e:  # a dead watcher thread never flips READY again (#132); retry on the next change
                print(f"watcher: scan failed: {e!r}")
                trace.emit(
                    "Ledger → Watcher",
                    f"tail {LEDGER_PATH}",
                    f"scan failed: {e!r:.120}",
                    132,
                    ["ledger", "watcher"],
                    ["tail"],
                )
        reap()
        time.sleep(POLL_SECS)
