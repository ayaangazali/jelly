"""The proxy on :4141. POST /v1/chat/completions is #13.

The client's bearer token is the session id (contracts §2); it never goes upstream. The frontier sees only the
server-side key (upstream.py). Upstream bytes are streamed through as they arrive; errors keep their status and body.

Plug-in points, so #17 #35 #20 #37 #24 #26 never edit this file:
- Every module in graduate/router/ is imported at startup (bottom of this file) and plugs in at import time.
- `register_on_call(fn)`: after each model call, once the last byte has gone to the client, the router runs
  `fn(session_id, request, response, usage, latency_ms, upstream, model)` in a worker thread, off the stream's path.
    request     the Chat Completions body exactly as the client sent it
    response    the upstream JSON (non-stream) or the list of parsed `chat.completion.chunk` dicts (stream)
    usage       `{input_tokens, cached_input_tokens, output_tokens}` (contracts §3); zeros if the upstream sent none
    latency_ms  request received to last byte sent
    upstream    "frontier" or "owned"; model is the id actually used
  Streamed calls ask the upstream for `stream_options.include_usage`, so the last chunk carries usage.
  A hook that raises is logged and skipped (fail open). Failed upstream calls (4xx/5xx) run no hooks.
- `register_route(fn)`: before each call, `fn(session_id, request)` (sync or async) may return a Response to serve
  instead of the frontier (the owned route, #20/#37). The first non-None wins. Whoever produces that Response calls
  `call_hooks(...)` when its last byte is sent.
- `app.include_router(...)` for new endpoints (/state #24, /api/sessions #17 #35, /v1/messages #26).
"""

import importlib
import inspect
import json
import logging
import pkgutil
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import (
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from starlette.background import BackgroundTask

import graduate.router
from graduate import trace
from graduate.router import upstream as frontier

log = logging.getLogger("uvicorn.error")
app = FastAPI(title="GRADUATE router")
_on_call = []
_routes = []


def register_on_call(fn):
    _on_call.append(fn)
    return fn


def register_route(fn):
    _routes.append(fn)
    return fn


def call_hooks(
    session_id, request, response, latency_ms, upstream="frontier", model=frontier.MODEL
):
    chunks = response if isinstance(response, list) else [response]
    raw = next((c["usage"] for c in reversed(chunks) if c.get("usage")), None) or {}
    usage = {
        "input_tokens": raw.get("prompt_tokens", 0),
        "cached_input_tokens": (raw.get("prompt_tokens_details") or {}).get(
            "cached_tokens", 0
        ),
        "output_tokens": raw.get("completion_tokens", 0),
    }
    for fn in _on_call:
        try:
            fn(session_id, request, response, usage, latency_ms, upstream, model)
        except Exception:
            log.exception("on_call hook %r failed", fn)


def _finish(session_id, request, raw, start):
    latency_ms = round((time.monotonic() - start) * 1000)
    try:
        if request.get("stream"):
            lines = bytes(raw).decode("utf-8", "replace").splitlines()
            response = [
                json.loads(l[5:])
                for l in lines
                if l.startswith("data:") and l[5:].strip() != "[DONE]"
            ]
        else:
            response = json.loads(raw)
    except ValueError:
        log.warning("session %s: upstream body is not JSON, hooks skipped", session_id)
        return
    call_hooks(session_id, request, response, latency_ms)


@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"


@app.get("/v1/models")
def models():
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "owned_by": "graduate"}
            for m in (frontier.MODEL, "graduate")
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    start = time.monotonic()
    body = await request.json()
    bearer = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    session_id = bearer if bearer.startswith("sess-") else "sess-anon"
    for route in _routes:
        served = route(session_id, body)
        if inspect.isawaitable(served):
            served = await served
        if served is not None:
            return served

    stream = bool(body.get("stream"))
    sent = dict(body, model=frontier.MODEL)
    if stream:
        sent["stream_options"] = {
            **(body.get("stream_options") or {}),
            "include_usage": True,
        }
    call, nodes, edges = (
        f"POST {frontier.URL}",
        ["opencode", "router", "openai"],
        ["chat", "frontier"],
    )
    try:
        resp = await frontier.send(sent)
    except httpx.HTTPError as e:
        trace.emit(
            "Router → OpenAI", call, f"error: {e!r}", 13, nodes, edges, session_id
        )
        return JSONResponse(
            {
                "error": {
                    "message": f"frontier unreachable: {e!r}",
                    "type": "upstream_error",
                }
            },
            502,
        )
    log.info(
        "session %s -> frontier %s: %s", session_id, frontier.MODEL, resp.status_code
    )
    trace.emit(
        "Router → OpenAI",
        call,
        f"{resp.status_code} · {frontier.MODEL} · {'stream' if stream else 'json'}",
        13,
        nodes,
        edges,
        session_id,
    )
    media_type = resp.headers.get("content-type")

    if resp.status_code >= 400 or not stream:
        content = await resp.aread()
        await resp.aclose()
        done = (
            BackgroundTask(_finish, session_id, body, content, start)
            if resp.status_code < 400
            else None
        )
        return Response(
            content, resp.status_code, media_type=media_type, background=done
        )

    raw = bytearray()

    async def relay():
        try:
            async for piece in resp.aiter_bytes():
                raw.extend(piece)
                yield piece
        finally:
            await resp.aclose()

    return StreamingResponse(
        relay(),
        resp.status_code,
        media_type=media_type,
        background=BackgroundTask(_finish, session_id, body, raw, start),
    )


for _m in pkgutil.iter_modules(graduate.router.__path__):
    try:
        importlib.import_module(f"graduate.router.{_m.name}")
    except Exception:
        log.exception("router plug-in %s failed to import; skipped", _m.name)


if (
    __name__ == "__main__"
):  # self-check against a mock frontier: python -m graduate.router.app
    import asyncio
    import os

    trace.TRACE_PATH = os.devnull
    os.environ["OPENAI_API_KEY"] = "sk-server"
    seen, calls = [], []
    sse = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":2,"prompt_tokens_details":{"cached_tokens":5}}}\n\ndata: [DONE]\n\n'

    def fake_openai(req):
        seen.append((req.headers["authorization"], json.loads(req.content)))
        if json.loads(req.content)["messages"] == "bad":
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        if json.loads(req.content).get("stream"):
            return httpx.Response(
                200, content=sse, headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 3},
            },
        )

    async def main():
        frontier.client = httpx.AsyncClient(transport=httpx.MockTransport(fake_openai))
        register_on_call(lambda *a: calls.append(a))
        c = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        )
        h = {"Authorization": "Bearer sess-0123456789ab"}
        r = await c.post(
            "/v1/chat/completions",
            headers=h,
            json={"model": "graduate", "stream": True, "messages": [], "x_unknown": 1},
        )
        assert r.status_code == 200 and r.content == sse, r.content
        auth, sent = seen[-1]
        assert (
            auth == "Bearer sk-server"
            and sent["model"] == frontier.MODEL
            and sent["x_unknown"] == 1
        )
        assert sent["stream_options"] == {"include_usage": True}
        sid, req, chunks, usage, *_ = calls[-1]
        assert (
            sid == "sess-0123456789ab"
            and req["model"] == "graduate"
            and len(chunks) == 2
        )
        assert usage == {
            "input_tokens": 7,
            "cached_input_tokens": 5,
            "output_tokens": 2,
        }
        r = await c.post("/v1/chat/completions", json={"messages": []})
        assert (
            r.json()["choices"][0]["message"]["content"] == "hi"
            and calls[-1][0] == "sess-anon"
        )
        assert calls[-1][3]["input_tokens"] == 3
        r = await c.post("/v1/chat/completions", headers=h, json={"messages": "bad"})
        assert (
            r.status_code == 429
            and r.json() == {"error": {"message": "slow down"}}
            and len(calls) == 2
        )

    asyncio.run(main())
    print("router self-check ok")
