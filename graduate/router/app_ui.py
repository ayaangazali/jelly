"""GET /app: the product frontend (ui/app/). Its CSS and JS load from /ui/app/ through state.py's /ui mount; every
number on it comes from the live APIs (/state, /api/swarm, /api/consent, /api/sample, /api/race).

GET /api/race feeds its Compare page: one pair per owned run in the ledger, raced against the newest frontier run of
the same prompt (a first-try run before an escalation rerun), each with its session log (null when none was kept),
plus the frontier rerun that rescued the owned run if it failed. Newest owned run first. `big_model` is the host the
router sends frontier calls to, so the story can say when that is a stand-in rather than OpenAI."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException
from fastapi.responses import FileResponse

from graduate.router.app import app
from graduate.router import sessionlog, state, upstream

PAGE = Path(__file__).resolve().parents[2] / "ui" / "app" / "index.html"


@app.get("/app", include_in_schema=False)
@app.get("/app/{path:path}", include_in_schema=False)
def product_app(path: str = ""):
    return FileResponse(PAGE, media_type="text/html")


def _log(session_id):
    try:
        return sessionlog.session_log(session_id)
    except HTTPException:
        return None


@app.get("/api/race")
def race():
    rows = state.jsonl("ledger.jsonl", 10_000)
    pairs = []
    for owned in reversed([r for r in rows if r.get("routed_to") == "owned"]):
        same = [r for r in rows if r.get("routed_to") == "frontier" and r.get("prompt") == owned.get("prompt")]
        frontier = next((r for r in reversed(same) if not r.get("escalated_from")), same[-1] if same else None)
        if frontier is None:
            continue
        rescue = next((r for r in rows if r.get("escalated_from") == owned["session_id"]), None)
        pairs.append(
            {
                "frontier": {"row": frontier, "log": _log(frontier["session_id"])},
                "owned": {"row": owned, "log": _log(owned["session_id"])},
                "rescue": rescue,
            }
        )
    return {"pairs": pairs, "big_model": urlparse(upstream.BASE_URL).netloc}  # api.openai.com, or a stand-in


def _steps(log):
    """`name first-arg` per tool call in a session log, the lines the showcase streams."""
    out = []
    for call in log or []:
        for t in (call.get("response") or {}).get("tool_calls") or []:
            try:
                arg = next(iter(json.loads(t["function"]["arguments"]).values()), "")
            except (ValueError, AttributeError, StopIteration):
                arg = ""
            out.append(f"{t['function']['name']} {str(arg).splitlines()[0] if arg else ''}"[:90])
    return out[:12]


@app.get("/api/replay")
def replay():
    """The showcase's real data: every ledger run with its tool-call steps, and each task type's newest loss curve
    (data/<task_type>.loss.jsonl, or a checkpoint's under data/checkpoints/)."""
    runs = [{**r, "steps": _steps(_log(r.get("session_id")))} for r in state.jsonl("ledger.jsonl", 2000)]
    loss = {}
    curves = sorted(Path("data").glob("**/*.loss.jsonl"), key=lambda p: p.stat().st_mtime) if Path("data").is_dir() else []
    for p in curves:
        name = p.name.removesuffix(".loss.jsonl")
        loss[re.sub(r"-v\d+$", "", name)] = {"name": name, "steps": state.jsonl(p, 1000)}
    return {"runs": runs, "loss": loss}


PROVIDER = re.compile(r"Memorable|GBrain|River|OpenAI|Anthropic|Superset")


@app.get("/api/provider-calls")
def provider_calls():
    """Every traced call to an outside provider, over the whole trace (up to its last 20,000 events), oldest first."""
    from graduate import trace

    return [e for e in state.jsonl(trace.TRACE_PATH, 20_000) if PROVIDER.search(str(e.get("who", "")))]
