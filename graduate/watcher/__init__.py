"""Ledger watcher: counts verified runs, flips READY (#19). Shape: graduate/contracts.md §1, §2, §5.

python -m graduate.watcher           tail ledger.jsonl, rescan whenever it changes
python -m graduate.watcher --once    replay the whole ledger once and exit
python -m graduate.watcher --check   self-check
"""

import json
import os
import re
import time

from graduate import registry, trace

LEDGER_PATH = "ledger.jsonl"
POLL_SECS = 1.0
NUMBERS = ("turns", "tool_calls", "cost_usd", "wall_secs")


def _rows():
    # Read the file directly: the row shape is the contract, ledger.py (#34) is the writer.
    try:
        with open(LEDGER_PATH, encoding="utf-8") as f:
            lines = f.read().split("\n")[:-1]  # drop a half-written last line
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in lines if line.strip()]


def _avg(rows):
    return {k: sum(r[k] for r in rows) / len(rows) for k in NUMBERS} if rows else None


def verify_pattern(commands):
    distinct = list(dict.fromkeys(commands))
    shapes = {re.sub(r"\d+", "*", c) for c in distinct}
    return shapes.pop() if len(distinct) > 1 and len(shapes) == 1 else distinct[0]


def scan():
    """Recompute every task type from the whole ledger. Same ledger in, same registry out."""
    # ponytail: full re-read per change; keep a byte offset if the ledger outgrows a demo day.
    rows = _rows()
    by_type = {}
    for r in rows:
        if r["task_type"] != "unknown":
            by_type.setdefault(r["task_type"], []).append(r)
    trace.emit(
        "Ledger → Watcher",
        f"tail {LEDGER_PATH}",
        f"{len(rows)} rows, {len(by_type)} task types",
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
        entry = known.get(t, {})
        commands = [r["verify_command"] for r in rs if r.get("verify_command")]
        if commands and not entry.get("verify_command"):
            fields["verify_command"] = verify_pattern(commands)
        if entry.get("title", t) == t:
            fields["title"] = t.replace("-", " ").capitalize()
        slugs = [r["procedure_slug"] for r in rs if r["procedure_slug"]]
        if slugs:
            fields["procedure_slug"] = slugs[-1]
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
            scan()
        time.sleep(POLL_SECS)
