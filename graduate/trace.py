"""Trace events for the live Under the hood view. Shape: graduate/contracts.md §8."""
import json
from collections import deque
from datetime import datetime, timezone

TRACE_PATH = "trace.jsonl"
TERMINAL_PATH = "terminal.log"
_recent = deque(maxlen=200)


def emit(who, call, result, issue, nodes=(), edges=(), session_id=None):
    event = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
        "who": who,
        "call": call,
        "result": result,
        "issue": issue,
        "nodes": list(nodes),
        "edges": list(edges),
    }
    _recent.append(event)
    with open(TRACE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    return event


def recent(n=200):
    return list(_recent)[-n:]


def terminal(line):
    with open(TERMINAL_PATH, "a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")
