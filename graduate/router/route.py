import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter

from graduate import trace
from graduate.router import classify as classifier
from graduate.router.app import app, register_route
from graduate.router.classify import classify

REGISTRY = Path(os.environ.get("GRADUATE_REGISTRY", "registry.json"))
_registry = {"mtime": None, "data": {"task_types": {}}}
_announced = set()


def registry():
    try:
        mtime = REGISTRY.stat().st_mtime
    except FileNotFoundError:
        return {"task_types": {}}
    if mtime != _registry["mtime"]:
        _registry["data"] = json.loads(REGISTRY.read_text())
        _registry["mtime"] = mtime
    return _registry["data"]


def first_user_text(request):
    for m in request.get("messages", []):
        if m.get("role") == "user":
            c = m.get("content")
            return c if isinstance(c, str) else " ".join(p.get("text", "") for p in c or [] if isinstance(p, dict))
    return ""


def decide(session_id, request, headers, hint=None):
    task_type, _ = classify(session_id, first_user_text(request), hint=hint)
    entry = registry()["task_types"].get(task_type, {})
    state = entry.get("state", "LEARNING")
    force = (headers.get("x-graduate-force") or "").lower()
    owned = force == "owned" or (force != "frontier" and state == "GRADUATED" and entry.get("model"))
    decision = {
        "task_type": task_type,
        "state": state,
        "upstream": "owned" if owned else "frontier",
        "model": entry.get("model") if owned else None,
        "serving": entry.get("serving") if owned else None,
        "deployment": entry.get("deployment") if owned else None,
    }
    if session_id not in _announced:
        _announced.add(session_id)
        why = "forced by header" if force in ("owned", "frontier") else state
        trace.emit("Router → registry.json", f'registry["{task_type}"].state',
                   f"{why} → route to {'your River model' if owned else 'frontier'}", 20,
                   nodes=["router", "registry", "river" if owned else "openai"],
                   edges=["reads", "owned" if owned else "frontier"], session_id=session_id)
    return decision


_registered = {}
_unwired = set()
router = APIRouter()


@router.post("/api/sessions")
def register_session(body: dict):
    session_id = str(body.get("session_id", ""))
    if not session_id.startswith("sess-"):
        return {"ok": False, "error": "session_id must start with sess-"}
    _registered[session_id] = {k: body.get(k) for k in ("prompt", "repo", "verify", "force_frontier", "task_type")}
    return {"ok": True}


def task_type_of(session_id):
    hit = classifier._cache.get(session_id)
    return hit[0] if hit else "unknown"


@register_route
async def classify_and_route(session_id, request):
    if session_id == "sess-anon":
        return None
    reg = _registered.get(session_id, {})
    headers = {"x-graduate-force": "frontier"} if reg.get("force_frontier") else {}
    d = await asyncio.to_thread(decide, session_id, request, headers, reg.get("task_type"))
    if d["upstream"] != "owned":
        return None
    from graduate.router import river
    serve = getattr(river, "stream_completion", None)
    if serve is None:
        if d["task_type"] not in _unwired:
            _unwired.add(d["task_type"])
            trace.emit("Router → River", "graduate.router.river.stream_completion", "not built yet (#37) → serving from frontier", 37,
                       nodes=["router", "river"], edges=["owned"], session_id=session_id)
        return None
    return await serve(request, d)


app.include_router(router)
