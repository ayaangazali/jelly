"""GET /api/swarm for the dashboard's #/swarm view: the newest `graduate swarm` run record (swarm/latest.json) plus
the last 50 A2A trace events (edges a2a-read / a2a-write). Shape: fixtures/swarm.example.json."""

import json
from pathlib import Path

from fastapi import APIRouter

from graduate import trace
from graduate.router.app import app
from graduate.router import state  # module, not names: state may import us mid-load via app.py

router = APIRouter()
NO_SWARM = {
    "error": "No swarm in this directory yet. Run `graduate swarm --tasks 01,02,03 --agents 3 --offline`.",
    "agents": [],
}
_last = {"run": NO_SWARM}


@router.get("/api/swarm")
def swarm():
    try:
        _last["run"] = json.loads(Path("swarm/latest.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        _last["run"] = NO_SWARM
    except ValueError:
        pass  # caught mid-rewrite: keep the last whole record
    a2a = [
        e
        for e in state.jsonl(trace.TRACE_PATH, 2000)
        if {"a2a-read", "a2a-write"} & set(e.get("edges") or ())
    ]
    return {**_last["run"], "a2a": a2a[-50:]}


app.include_router(router)
