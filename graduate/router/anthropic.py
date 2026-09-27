"""Stretch: Anthropic /v1/messages (#26)."""

import json
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from graduate.router.app import app, chat_completions
from graduate.router.sessionlog import message

STOP = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use"}
CHOICE = {"auto": "auto", "any": "required", "none": "none"}


def _text(content):
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content or [] if b.get("type") == "text")


def to_openai(body, prompt_id):
    messages = [{"role": "system", "content": _text(body["system"])}] if body.get("system") else []
    for m in body["messages"]:
        blocks = m["content"]
        if isinstance(blocks, str):
            messages.append({"role": m["role"], "content": blocks})
        elif m["role"] == "assistant":
            calls = [
                {"id": b["id"], "type": "function", "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
                for b in blocks
                if b.get("type") == "tool_use"
            ]
            messages.append({"role": "assistant", "content": _text(blocks) or None, **({"tool_calls": calls} if calls else {})})
        else:
            for b in blocks:
                if b.get("type") == "tool_result":
                    messages.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": _text(b.get("content"))})
            if _text(blocks):
                messages.append({"role": "user", "content": _text(blocks)})
    out = {"model": body.get("model"), "messages": messages, "stream": bool(body.get("stream"))}
    if body.get("max_tokens"):
        out["max_completion_tokens"] = body["max_tokens"]
    if body.get("stop_sequences"):
        out["stop"] = body["stop_sequences"]
    tools = [
        {"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t["input_schema"]}}
        for t in body.get("tools") or []
        if "input_schema" in t
    ]
    if tools:
        out["tools"] = tools
        choice = body.get("tool_choice") or {}
        if choice.get("type") == "tool":
            out["tool_choice"] = {"type": "function", "function": {"name": choice["name"]}}
        elif choice.get("type") in CHOICE:
            out["tool_choice"] = CHOICE[choice["type"]]
    if prompt_id:
        out["user"] = prompt_id
    return out


def _usage(u):
    cached = ((u or {}).get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    return {
        "input_tokens": (u or {}).get("prompt_tokens", 0) - cached,
        "cache_read_input_tokens": cached,
        "output_tokens": (u or {}).get("completion_tokens", 0),
    }


def to_anthropic(body, model):
    m = message(body)
    content = [{"type": "text", "text": m["content"]}] if m["content"] else []
    content += [
        {"type": "tool_use", "id": c["id"], "name": c["function"]["name"], "input": json.loads(c["function"]["arguments"] or "{}")}
        for c in m.get("tool_calls", [])
    ]
    return {
        "id": f"msg_{uuid.uuid4().hex}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": STOP.get(m["finish_reason"], "end_turn"),
        "stop_sequence": None,
        "usage": _usage(body.get("usage")),
    }


def _event(kind, **data):
    return f"event: {kind}\ndata: {json.dumps({'type': kind, **data})}\n\n".encode()


async def to_sse(chunks, model):
    yield _event("message_start", message={**to_anthropic({"choices": [{"message": {}}]}, model), "stop_reason": None})
    block, open_kind, calls, stop, usage, buf = -1, None, {}, None, None, b""
    async for piece in chunks:
        buf += piece
        *lines, buf = buf.split(b"\n")
        for line in lines:
            if not line.startswith(b"data:") or line[5:].strip() == b"[DONE]":
                continue
            chunk = json.loads(line[5:])
            usage = chunk.get("usage") or usage
            for choice in chunk.get("choices") or []:
                if choice.get("index", 0):
                    continue
                delta = choice.get("delta") or {}
                stop = choice.get("finish_reason") or stop
                if delta.get("content"):
                    if open_kind != "text":
                        if open_kind is not None:
                            yield _event("content_block_stop", index=block)
                        block, open_kind = block + 1, "text"
                        yield _event("content_block_start", index=block, content_block={"type": "text", "text": ""})
                    yield _event("content_block_delta", index=block, delta={"type": "text_delta", "text": delta["content"]})
                for t in delta.get("tool_calls") or []:
                    fn = t.get("function") or {}
                    if t.get("index", 0) not in calls:
                        if open_kind is not None:
                            yield _event("content_block_stop", index=block)
                        block, open_kind = block + 1, "tool"
                        calls[t.get("index", 0)] = block
                        yield _event(
                            "content_block_start",
                            index=block,
                            content_block={"type": "tool_use", "id": t.get("id"), "name": fn.get("name"), "input": {}},
                        )
                    if fn.get("arguments"):
                        yield _event(
                            "content_block_delta",
                            index=calls[t.get("index", 0)],
                            delta={"type": "input_json_delta", "partial_json": fn["arguments"]},
                        )
    if open_kind is not None:
        yield _event("content_block_stop", index=block)
    yield _event(
        "message_delta",
        delta={"stop_reason": STOP.get(stop, "end_turn"), "stop_sequence": None},
        usage=_usage(usage),
    )
    yield _event("message_stop")


@app.post("/v1/messages")
async def messages(request: Request):
    body = await request.json()
    key = request.headers.get("x-api-key") or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    translated = json.dumps(to_openai(body, request.headers.get("x-claude-code-prompt-id"))).encode()

    async def receive():
        return {"type": "http.request", "body": translated, "more_body": False}

    inner = Request(
        {"type": "http", "method": "POST", "path": "/v1/chat/completions", "headers": [(b"authorization", f"Bearer {key}".encode())]},
        receive,
    )
    resp = await chat_completions(inner)
    if resp.status_code >= 400:
        return JSONResponse(
            {"type": "error", "error": {"type": "api_error", "message": bytes(resp.body).decode("utf-8", "replace")}},
            resp.status_code,
        )
    if isinstance(resp, StreamingResponse):
        return StreamingResponse(to_sse(resp.body_iterator, body.get("model")), media_type="text/event-stream", background=resp.background)
    return JSONResponse(to_anthropic(json.loads(resp.body), body.get("model")), background=resp.background)
