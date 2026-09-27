"""Owned-model serving (#37): a graduated session's calls answered from its checkpoint, in OpenAI shape.

route.py (#20) calls `stream_completion(request, session)` when the registry says the task type is GRADUATED;
`session` is its routing decision plus `session_id`. The backend comes from graduate.registrar.train: the local
LoRA checkpoint on this machine's CPU, or River for a river:// checkpoint. The whole answer is generated first,
then sent as a synthesized SSE stream (role and content, one chunk per tool call, finish, usage) or as one JSON
body. Any error returns None, so the frontier serves that call (fail open) and the event log says so.
"""

import asyncio
import json
import time
import uuid

from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from graduate import registry, trace
from graduate.registrar import train
from graduate.router.app import call_hooks


def _chunks(cid, model, msg, finish, usage):
    head = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
    }
    deltas = [{"role": "assistant", "content": msg["content"]}]
    deltas += [
        {"tool_calls": [dict(c, index=i)]}
        for i, c in enumerate(msg.get("tool_calls", []))
    ]
    out = [
        {**head, "choices": [{"index": 0, "delta": d, "finish_reason": None}]}
        for d in deltas
    ]
    out.append(
        {**head, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]}
    )
    out.append({**head, "choices": [], "usage": usage})
    return out


async def stream_completion(request, session):
    sid, model, task_type = (
        session.get("session_id", "sess-anon"),
        session["model"],
        session["task_type"],
    )
    start = time.monotonic()
    try:
        msg, used = await asyncio.to_thread(
            train.backend(model).complete,
            model,
            request["messages"],
            request.get("tools"),
        )
    except Exception as e:
        trace.emit(
            "Router → River",
            f'complete(messages, checkpoint_path="{model}")',
            f"{e!r:.120} → frontier serves this call",
            37,
            ["router", "river", "openai"],
            ["owned", "frontier"],
            session_id=sid,
        )
        registry.add_event(
            "error",
            task_type,
            f"Your model for {task_type} failed a call ({str(e) or type(e).__name__}); the frontier answered it.",
        )
        return None
    usage = {
        "prompt_tokens": used.get("prompt_tokens", 0),
        "completion_tokens": used.get("completion_tokens", 0),
        "total_tokens": used.get("prompt_tokens", 0) + used.get("completion_tokens", 0),
        "prompt_tokens_details": {"cached_tokens": 0},
    }
    finish = "tool_calls" if msg.get("tool_calls") else "stop"
    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    ms = round((time.monotonic() - start) * 1000)
    tools = (
        ", ".join(c["function"]["name"] for c in msg.get("tool_calls", [])) or "text"
    )
    trace.emit(
        "Router → River",
        f'complete(messages, checkpoint_path="{model}")',
        f"200 · {usage['completion_tokens']} output tokens · {tools} · {ms} ms",
        37,
        ["router", "river"],
        ["owned"],
        session_id=sid,
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
                call_hooks, sid, request, body, ms, "owned", model
            ),
        )
    chunks = _chunks(cid, model, msg, finish, usage)
    sent = (
        chunks
        if (request.get("stream_options") or {}).get("include_usage")
        else chunks[:-1]
    )
    sse = "".join(f"data: {json.dumps(c)}\n\n" for c in sent) + "data: [DONE]\n\n"
    return StreamingResponse(
        iter([sse]),
        media_type="text/event-stream",
        background=BackgroundTask(call_hooks, sid, request, chunks, ms, "owned", model),
    )
