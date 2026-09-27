import json
import os
from pathlib import Path

from graduate import trace
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
