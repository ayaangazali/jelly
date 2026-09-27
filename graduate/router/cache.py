"""Verified-response cache (#144), in front of the smart router.

A turn whose normalized request (messages + tools) exactly matches a turn of an earlier verified frontier session is
answered from that session's log: $0, milliseconds, no model call. The runner's verify still decides the session.
- Indexed: ledger rows with exit 0, not tampered, not forced to fail, not an escalation rerun, routed_to "frontier",
  and only their frontier-served lines. Owned, mixed and cache sessions never are, so a gamed run can't replay.
- The key is the whole message prefix plus the tools list, so every tool result (file contents, test output) is in
  it, and another harness never gets this one's answer. Paths under OpenCode's working directory and the date in its
  <env> block, skill locations and the runner's A2A notes are normalized; a replayed answer's paths are mapped back to the asking session's directory.
- A session that was served from cache and then failed or was tampered gets every answer it was served evicted: the
  ledger names the session, its log the keys and their source sessions. Another verified session may still answer
  the same key.
- In memory only, rebuilt from ledger.jsonl and sessions/ when the ledger's mtime changes. Nothing is written.
- Fail open: any error, a missing or corrupt file, a sess-anon call (no verify decides it) or a forced-frontier session
  (an escalation rerun) goes on to route.py and the frontier as before.
Order: the hook goes first in the router's route list, before route.py's (the smart router), whichever module was
imported first. The app import comes before the other router modules': app.py imports every plug-in, and one that
finds sessionlog half-imported would be skipped.
GET /api/cache: hit rate and $ saved over metrics.jsonl, entries and evicted keys in the index.
"""

import hashlib
import json
import re
import time
import uuid
from pathlib import Path

from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from graduate.router import app as router  # first: see the docstring
from graduate.router.app import app, call_hooks, log
from graduate import ledger, trace
from graduate.registrar.dataset import _WORKDIR, relative
from graduate.router import metrics, route, sessionlog
from graduate.router.river import _chunks

ISSUE = 144
# Per-run text, matched inside JSON text: OpenCode's date line, the A2A notes the runner puts before the task (they
# name the last passing session, so no two runs would share a key), and skill locations (a skill installed in two
# directories is listed from either one, run to run; seen on a real rerun).
_DATE = re.compile(r"(Today's date: |<location>)[^\\\"<]*")
_NOTES = re.compile(r"## Notes from other agents\\n.*?\\n\\n")
_index = {"mtime": None, "keys": {}, "evicted": {}}


def _roots(request):
    system = next(
        (
            m["content"]
            for m in request.get("messages") or []
            if m.get("role") == "system" and isinstance(m.get("content"), str)
        ),
        "",
    )
    return [d.rstrip("/") for d in _WORKDIR.findall(system)]


def key(request):
    text = _NOTES.sub("", _DATE.sub(r"\1-", json.dumps(request.get("messages") or [])))
    messages = json.loads(text)
    canon = {"messages": relative(messages), "tools": request.get("tools") or []}
    return hashlib.sha256(
        json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def eligible(row):
    return (
        row.get("routed_to") == "frontier"
        and row.get("exit_code") == 0
        and row.get("tampered") is False
        and row.get("forced_failure") is False
        and row.get("escalated_from") is None
    )


def _jsonl(path):
    """A truncated or corrupt line (#125) drops that line only; a missing file is empty."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def index():
    try:
        mtime = Path(ledger.LEDGER_PATH).stat().st_mtime_ns
    except OSError:
        mtime = None
    if mtime == _index["mtime"]:
        return _index
    rows = _jsonl(ledger.LEDGER_PATH)
    logs = {
        r.get("session_id"): [
            l
            for l in _jsonl(sessionlog.SESSIONS_DIR / f"{r.get('session_id')}.jsonl")
            if isinstance(l, dict) and "request" in l
        ]
        for r in rows
    }
    evicted = {  # (key, source session) of every answer replayed into a session that then didn't verify
        (key(l["request"]), l.get("model", "").removeprefix("cache:")): r["session_id"]
        for r in rows
        if r.get("exit_code") != 0 or r.get("tampered")
        for l in logs[r.get("session_id")]
        if l.get("upstream") == "cache"
    }
    keys = {}
    for r in filter(eligible, rows):
        for l in logs[r["session_id"]]:
            k = key(l["request"])
            if l.get("upstream") == "frontier" and (k, r["session_id"]) not in evicted:
                keys.setdefault(k, (l["response"], _roots(l["request"]), r["session_id"], l.get("usage") or {}))
    for (k, src), sid in evicted.items() - _index["evicted"].items():
        trace.emit("Router → Cache", f"evict {k[:12]}", f"{sid} failed verify · {src}'s answer evicted", ISSUE,
                   ["router", "cache"], ["cache"], sid)
    _index.update(mtime=mtime, keys=keys, evicted=evicted)
    return _index


def _replay(session_id, request):
    if session_id == "sess-anon":
        return None
    if route._registered.get(session_id, {}).get("force_frontier"):
        return None
    entries = index()["keys"]
    if not entries:
        return None
    start = time.monotonic()
    k = key(request)
    hit = entries.get(k)
    if hit is None:
        trace.emit(
            "Router → Cache",
            f"lookup {k[:12]}",
            f"miss · {len(entries)} entries → smart router",
            ISSUE,
            ["router", "cache"],
            ["cache"],
            session_id,
        )
        return None
    msg, roots, src, used = hit
    text = json.dumps({k: v for k, v in msg.items() if k != "finish_reason"})
    for old, new in zip(
        roots, _roots(request)
    ):  # the source session's directory → this session's
        text = text.replace(json.dumps(old)[1:-1], json.dumps(new)[1:-1])
    msg = json.loads(text)
    model, cid = f"cache:{src}", f"chatcmpl-{uuid.uuid4().hex[:24]}"
    finish = "tool_calls" if msg.get("tool_calls") else "stop"
    usage = {  # the source call's tokens: what the frontier would have charged; metrics prices "cache" at $0
        "prompt_tokens": used.get("input_tokens", 0),
        "completion_tokens": used.get("output_tokens", 0),
        "total_tokens": used.get("input_tokens", 0) + used.get("output_tokens", 0),
        "prompt_tokens_details": {"cached_tokens": used.get("cached_input_tokens", 0)},
    }
    ms = round((time.monotonic() - start) * 1000)
    tools = (
        ", ".join(c["function"]["name"] for c in msg.get("tool_calls", [])) or "text"
    )
    trace.emit(
        "Router → Cache",
        f"lookup {k[:12]}",
        f"hit · {src} · {tools} · $0 · {ms} ms",
        ISSUE,
        ["router", "cache"],
        ["cache"],
        session_id,
    )
    if not request.get("stream"):
        body = {
            "id": cid,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
            "usage": usage,
        }
        return JSONResponse(
            body,
            background=BackgroundTask(
                call_hooks, session_id, request, body, ms, "cache", model
            ),
        )
    chunks = _chunks(cid, model, {"content": "", **msg}, finish, usage)
    sent = (
        chunks
        if (request.get("stream_options") or {}).get("include_usage")
        else chunks[:-1]
    )
    sse = "".join(f"data: {json.dumps(c)}\n\n" for c in sent) + "data: [DONE]\n\n"
    return StreamingResponse(
        iter([sse]),
        media_type="text/event-stream",
        background=BackgroundTask(
            call_hooks, session_id, request, chunks, ms, "cache", model
        ),
    )


def replay(session_id, request):
    try:
        return _replay(session_id, request)
    except Exception:
        log.exception("cache: lookup failed; the router serves this call")
        return None


router._routes.insert(0, replay)  # before route.py's hook: see the docstring


@app.get("/api/cache")
def stats():
    """Cache turns over all model calls in metrics.jsonl, and what the frontier would have charged for them."""
    recs = _jsonl(metrics.METRICS_PATH)
    hits = [r for r in recs if r.get("upstream") == "cache"]
    i = index()
    return {
        "turns": len(recs),
        "hits": len(hits),
        "hit_rate": round(len(hits) / len(recs), 4) if recs else 0.0,
        "saved_usd": round(sum(r.get("saved_usd", 0) for r in hits), 6),
        "sessions": len({r.get("session_id") for r in hits}),
        "entries": len(i["keys"]),
        "evicted": len(i["evicted"]),
    }
