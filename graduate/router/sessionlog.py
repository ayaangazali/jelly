"""Session log sessions/<id>.jsonl (#35). Shape: graduate/contracts.md §3.

One line per model call, appended by the router's on_call hook after the last byte went to the client, so it never
slows the stream. `request` is the client's body as received (it never holds the upstream key). Streamed responses
are reassembled into the same message a non-streamed call returns. GET /api/sessions/<id>/log returns the lines.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from graduate import trace
from graduate.router.app import app, register_on_call

SESSIONS_DIR = Path("sessions")
_NAME = re.compile(r"sess-[\w-]+")  # the bearer becomes a file name: no slashes or dots


def message(response):
    """`{role, content, tool_calls?, finish_reason}` from a non-stream body or a list of stream chunks."""
    if not isinstance(response, list):
        choice = response["choices"][0]
        m = choice["message"]
        out = {"role": m.get("role") or "assistant", "content": m.get("content") or ""}
        if m.get("tool_calls"):
            out["tool_calls"] = m["tool_calls"]
        out["finish_reason"] = choice.get("finish_reason")
        return out
    out, calls, finish = {"role": "assistant", "content": ""}, {}, None
    for chunk in response:
        for choice in chunk.get("choices") or []:
            if choice.get("index", 0):
                continue  # n > 1: keep the first choice, like the non-stream path
            delta = choice.get("delta") or {}
            out["content"] += delta.get("content") or ""
            for t in delta.get("tool_calls") or []:
                c = calls.setdefault(
                    t.get("index", 0),
                    {
                        "id": None,
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                c["id"] = t.get("id") or c["id"]
                c["type"] = t.get("type") or c["type"]
                fn = t.get("function") or {}
                c["function"]["name"] += fn.get("name") or ""
                c["function"]["arguments"] += fn.get("arguments") or ""
            finish = choice.get("finish_reason") or finish
    if calls:
        out["tool_calls"] = [calls[i] for i in sorted(calls)]
    out["finish_reason"] = finish
    return out


def write(session_id, request, response, usage, latency_ms, upstream, model):
    if not _NAME.fullmatch(session_id):
        session_id = "sess-anon"
    line = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
        "upstream": upstream,
        "model": model,
        "request": request,
        "response": message(response),
        "usage": usage,
        "latency_ms": latency_ms,
    }
    SESSIONS_DIR.mkdir(exist_ok=True)
    with open(SESSIONS_DIR / f"{session_id}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    trace.emit(
        "Router → Session log",
        f"append sessions/{session_id}.jsonl",
        f"{upstream} · {model} · {latency_ms} ms",
        35,
        ["router", "disk"],
        ["log"],
        session_id,
    )


register_on_call(write)


@app.get("/api/sessions/{session_id}/log")
def session_log(session_id: str):
    path = SESSIONS_DIR / f"{session_id}.jsonl"
    if not _NAME.fullmatch(session_id) or not path.exists():
        raise HTTPException(404, f"no log for {session_id}")
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":  # self-check: python -m graduate.router.sessionlog
    import asyncio
    import os
    import tempfile

    import httpx

    os.chdir(tempfile.mkdtemp())  # sessions/ and trace.jsonl land in a scratch dir

    def call(i, name, args):
        return {"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": args}}

    def tc(index, arguments, **first):  # a tool_call delta; the first one for an index carries id, type, name
        name = first.pop("name", None)
        return {"index": index, **first, "function": {**({"name": name} if name else {}), "arguments": arguments}}

    # Fixture: one call with two parallel tool calls, as OpenAI returns it in JSON and as stream chunks. The
    # arguments arrive in fragments, and the second tool call starts before the first one's arguments end.
    plain = {
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "refusal": None,
                    "tool_calls": [
                        call(1, "read", '{"file_path": "calc/mod_05.py"}'),
                        call(2, "bash", '{"command": "pytest -q"}'),
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1400, "completion_tokens": 60},
    }
    deltas = [
        {"role": "assistant", "content": None, "refusal": None},
        {"tool_calls": [tc(0, "", id="call_1", type="function", name="read")]},
        {"tool_calls": [tc(0, '{"file_')]},
        {"tool_calls": [tc(1, "", id="call_2", type="function", name="bash")]},
        {"tool_calls": [tc(0, 'path": "calc/mod_05.py"}')]},
        {"tool_calls": [tc(1, '{"command": ')]},
        {"tool_calls": [tc(1, '"pytest -q"}')]},
        {},
    ]
    stream = [{"choices": [{"index": 0, "delta": d, "finish_reason": None}]} for d in deltas]
    stream[-1]["choices"][0]["finish_reason"] = "tool_calls"
    stream.append({"choices": [], "usage": plain["usage"]})
    assert message(stream) == message(plain), (message(stream), message(plain))
    assert message(plain) == {
        "role": "assistant",
        "content": "",
        "tool_calls": [call(1, "read", '{"file_path": "calc/mod_05.py"}'), call(2, "bash", '{"command": "pytest -q"}')],
        "finish_reason": "tool_calls",
    }
    text = [{"choices": [{"index": 0, "delta": {"content": p}, "finish_reason": None}]} for p in ("Fi", "xed.")]
    text[-1]["choices"][0]["finish_reason"] = "stop"
    assert message(text) == {"role": "assistant", "content": "Fixed.", "finish_reason": "stop"}

    # One file per session, one line per call; a bearer that isn't a plain name lands in sess-anon.
    usage = {"input_tokens": 1400, "cached_input_tokens": 0, "output_tokens": 60}
    req = {"model": "graduate", "stream": True, "messages": [{"role": "user", "content": "fix it"}]}
    write("sess-0123456789ab", req, stream, usage, 610, "frontier", "gpt-5.4")
    write("sess-0123456789ab", dict(req, stream=False), plain, usage, 580, "frontier", "gpt-5.4")
    write("sess-fedcba987654", req, text, usage, 600, "owned", "river://run/ckpt")
    write("sess-../../x", req, plain, usage, 1, "frontier", "gpt-5.4")
    assert sorted(os.listdir("sessions")) == ["sess-0123456789ab.jsonl", "sess-anon.jsonl", "sess-fedcba987654.jsonl"]
    rows = [json.loads(l) for l in open("sessions/sess-0123456789ab.jsonl")]
    assert len(rows) == 2 and rows[0]["response"] == rows[1]["response"] == message(plain)
    assert list(rows[0]) == ["ts", "session_id", "upstream", "model", "request", "response", "usage", "latency_ms"]
    assert rows[0]["request"] == req and rows[0]["usage"] == usage and rows[0]["latency_ms"] == 610
    ev = trace.recent()[-1]
    assert (ev["who"], ev["nodes"], ev["edges"], ev["issue"]) == ("Router → Session log", ["router", "disk"], ["log"], 35)

    async def get(path):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path)

    assert asyncio.run(get("/api/sessions/sess-0123456789ab/log")).json() == rows
    assert asyncio.run(get("/api/sessions/sess-000000000000/log")).status_code == 404
    print("sessionlog self-check ok")
