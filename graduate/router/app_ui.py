"""GET /app: the product frontend (ui/app/). Its CSS and JS load from /ui/app/ through state.py's /ui mount; every
number on it comes from the live APIs (/state, /api/swarm, /api/consent, /api/sample, /api/race).

GET /api/race feeds its Compare page: one pair per owned run in the ledger, raced against the newest frontier run of
the same prompt (a first-try run before an escalation rerun), each with its session log (null when none was kept),
plus the frontier rerun that rescued the owned run if it failed. Newest owned run first."""

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

from graduate.router.app import app
from graduate.router import sessionlog, state

PAGE = Path(__file__).resolve().parents[2] / "ui" / "app" / "index.html"


@app.get("/app", include_in_schema=False)
def product_app():
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
    return {"pairs": pairs}
