"""Per-call metrics.jsonl and per-session aggregates (#17). Shape: graduate/contracts.md §4, cost §9.

One record per model call, appended by the router's on_call hook after the last byte went to the client, so it
never slows the stream. `get_session(id)` is the sum of that session's records; `GET /api/sessions/<id>` serves it.
Aggregates are rebuilt from metrics.jsonl at import, so a router restart doesn't lose a session.
"""

import json
import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from graduate import trace
from graduate.router import upstream
from graduate.router.app import app, register_on_call
from graduate.router.route import task_type_of
from graduate.router.sessionlog import message

METRICS_PATH = Path("metrics.jsonl")
PRICES = json.loads(upstream._prices.read_text())
if upstream.MODEL != PRICES["frontier"]["model"]:
    if upstream.MODEL in upstream.LIST_PRICES:
        PRICES["frontier"] = {"model": upstream.MODEL, **upstream.LIST_PRICES[upstream.MODEL]}
    else:
        logging.getLogger("uvicorn.error").warning(
            "OPENAI_MODEL=%s has no known price: costs use %s's from %s; set its prices in that file's frontier block",
            upstream.MODEL, PRICES["frontier"]["model"], upstream._prices,
        )
SUMMED = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "tool_calls",
    "cost_usd",
)
_sessions = defaultdict(lambda: {"task_type": "unknown", **dict.fromkeys(("turns",) + SUMMED, 0)})
_lock = threading.Lock()


def cost(usage, role):
    """Contracts §9: cached input at the cached price, the rest at the input price. A cache replay (#144) is free."""
    if role == "cache":
        return 0.0
    p = PRICES[role]
    fresh = usage["input_tokens"] - usage["cached_input_tokens"]
    dollars = (
        fresh * p["input"]
        + usage["cached_input_tokens"] * p["cached_input"]
        + usage["output_tokens"] * p["output"]
    )
    return round(dollars / 1_000_000, 6)


def _add(rec):
    agg = _sessions[rec["session_id"]]
    agg["turns"] += 1
    agg["task_type"] = rec.get("task_type", "unknown")
    for k in SUMMED:
        agg[k] += rec[k]
    agg["cost_usd"] = round(
        agg["cost_usd"], 6
    )  # equals the file's sum, without float noise


def _load():
    if not METRICS_PATH.exists():
        return
    text = METRICS_PATH.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        try:
            with open(METRICS_PATH, "a", encoding="utf-8") as f:
                f.write("\n")
        except OSError:
            pass
    for line in text.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        _add(rec)


def record(session_id, request, response, usage, latency_ms, upstream, model):
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
        "task_type": task_type_of(session_id),
        "upstream": upstream,
        "model": model,
        **usage,
        "tool_calls": len(
            message(response).get("tool_calls", [])
        ),  # from the response, never the request
        "cost_usd": cost(usage, upstream),
        **({"saved_usd": cost(usage, "frontier")} if upstream == "cache" else {}),
        "latency_ms": latency_ms,
        "stream": bool(request.get("stream")),
    }
    with _lock:
        with open(METRICS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        _add(rec)
        turns = _sessions[session_id]["turns"]
    trace.emit(
        "Router → Metrics",
        "append metrics.jsonl",
        f"turn {turns} · {rec['input_tokens']} in ({rec['cached_input_tokens']} cached) · "
        f"{rec['output_tokens']} out · ${rec['cost_usd']}",
        17,
        ["router", "disk"],
        ["log"],
        session_id,
    )
    return rec


def get_session(session_id):
    """`{session_id, turns, input_tokens, cached_input_tokens, output_tokens, tool_calls, cost_usd}`; zeros if unseen."""
    with _lock:
        return {
            "session_id": session_id,
            **_sessions.get(session_id, _sessions.default_factory()),
        }


_load()
register_on_call(record)
app.get("/api/sessions/{session_id}")(get_session)


if __name__ == "__main__":  # self-check: python -m graduate.router.metrics
    import asyncio
    import os
    import tempfile
    import time

    import httpx

    # Importing app above already imported this file as graduate.router.metrics; that copy owns the hook and route.
    import graduate.router.metrics as m

    os.chdir(tempfile.mkdtemp())  # metrics.jsonl and trace.jsonl land in a scratch dir
    m._sessions.clear()
    s = "sess-0123456789ab"
    req = {"model": "graduate", "messages": [{"role": "user", "content": "fix it"}]}
    calls = [
        {
            "id": f"c{i}",
            "type": "function",
            "function": {"name": "bash", "arguments": "{}"},
        }
        for i in (1, 2)
    ]
    plain = {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "tool_calls": calls},
                "finish_reason": "tool_calls",
            }
        ]
    }
    chunks = [
        {
            "choices": [
                {"index": 0, "delta": {"content": "Fixed."}, "finish_reason": "stop"}
            ]
        },
        {"choices": [], "usage": {"prompt_tokens": 1500}},
    ]

    # §9 against the fixture's rows: 1847 fresh * 2.00 + 16384 cached * 0.20 + 412 out * 12.00, then the owned row.
    rows = [
        json.loads(l)
        for l in (m.upstream._prices.parent / "metrics.example.jsonl")
        .read_text()
        .splitlines()
    ]
    assert (
        [m.cost(r, r["upstream"]) for r in rows]
        == [r["cost_usd"] for r in rows]
        == [0.011915, 0.000511]
    )

    first = {"input_tokens": 1400, "cached_input_tokens": 0, "output_tokens": 60}
    second = {
        "input_tokens": 1500,
        "cached_input_tokens": 1280,
        "output_tokens": 40,
    }  # the cached prefix of call 1
    t = time.perf_counter()
    a = m.record(s, req, plain, first, 900, "frontier", "gpt-5.6-terra")
    ms = (time.perf_counter() - t) * 1000
    b = m.record(
        s, {**req, "stream": True}, chunks, second, 700, "frontier", "gpt-5.6-terra"
    )
    m.record("sess-anon", req, plain, first, 5, "owned", "river://ckpt")
    assert ms < 5, ms
    assert (a["tool_calls"], a["stream"], b["tool_calls"], b["stream"]) == (
        2,
        False,
        0,
        True,
    )
    assert (
        a["cost_usd"] == 0.00352 and b["cost_usd"] == 0.001176
    )  # 220*2.00 + 1280*0.20 + 40*12.00 = 1176

    written = [json.loads(l) for l in open("metrics.jsonl")]
    assert len(written) == 3 and all(
        list(r) == list(rows[0]) for r in written
    )  # the fixture's fields, in order
    mine = [r for r in written if r["session_id"] == s]
    want = {
        "session_id": s,
        "task_type": "unknown",
        "turns": 2,
        **{k: round(sum(r[k] for r in mine), 6) for k in SUMMED},
    }
    assert m.get_session(s) == want and m.get_session("sess-000000000000")["turns"] == 0
    assert [(e["who"], e["edges"], e["issue"]) for e in trace.recent()] == [
        ("Router → Metrics", ["log"], 17)
    ] * 3

    async def get(path):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=m.app), base_url="http://t"
        ) as c:
            return (await c.get(path)).json()

    assert asyncio.run(get(f"/api/sessions/{s}")) == want

    m._sessions.clear()  # a restarted router rebuilds the same aggregates from the file
    m._load()
    assert m.get_session(s) == want
    print(f"metrics self-check ok ({ms:.2f} ms per record)")
