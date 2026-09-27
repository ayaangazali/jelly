"""POST /api/chat-compare {"preset": "broken-09"} (captain's Chat page, /app/chat): one fixed task environment (a demo broken
state: source, test, real failing pytest output; GET /api/chat-preset), sent to the big model and your own model at the
same instant, streamed back as one SSE stream. A person may also send their own {"prompt": "..."} under the same caps.

Every event is `data: {"side": "big"|"small", "type": ...}`:
- `start`: that side's call is launched; `t_ms` is milliseconds since the request arrived (both ~0).
- `delta`: `text`, a piece of the answer. The big model streams token by token; River's checkpoint chat has no
  streaming, so your model's answer arrives as one piece.
- `done`: `output_tokens`, `input_tokens`, `cost_usd` (metrics.cost, prices.json), `wall_ms`, `model`.
- `error`: `message`, never a key or a raw upstream body.
Then one `{"type": "end"}`.

Public-internet safety: presets only (the prompt is built here, <= 2,000 chars), <= 400 output tokens per side, and chat-budget.json caps the total
at $5 and 200 requests; past either, a plain refusal. Each call goes through app.call_hooks, so metrics.jsonl (and
the pricing logs) get it like any routed call.
"""

import asyncio
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from graduate import registry, trace
from graduate.registrar import train
from graduate.router import metrics, upstream
from graduate.router.app import app, call_hooks

MAX_PROMPT = 2000
MAX_OUT = 400
MAX_USD = 5.0
MAX_REQUESTS = 200
BUDGET_PATH = Path("chat-budget.json")
BIG_MODEL = os.environ.get("CHAT_BIG_MODEL", "gpt-5.5")
OLD_SMALL = "river://9a2699b3-ce6f-4182-9da8-824a68de9c84/sampler_weights/fix-failing-test-v1"


def small_model():
    """CHAT_OWNED_MODEL, else the newest GRADUATED task type's river:// model in registry.json, else OLD_SMALL."""
    if env := os.environ.get("CHAT_OWNED_MODEL"):
        return env
    try:
        grads = [t for t in registry.load().get("task_types", {}).values() if t.get("state") == "GRADUATED" and str(t.get("model") or "").startswith("river://")]
    except Exception:
        grads = []
    return max(grads, key=lambda t: t.get("graduated_at") or "")["model"] if grads else OLD_SMALL
# The most one request can cost: 2,000 chars of prompt (<= 2,000 tokens) plus 400 output tokens, per side.
WORST = metrics.cost(
    {"input_tokens": MAX_PROMPT, "cached_input_tokens": 0, "output_tokens": MAX_OUT},
    "frontier",
) + metrics.cost(
    {"input_tokens": MAX_PROMPT, "cached_input_tokens": 0, "output_tokens": MAX_OUT},
    "owned",
)

ROOT = Path(__file__).resolve().parents[2]
# Fixed task environments (the public link cannot send its own prompt): demo broken state 09, planted the way
# scripts/reset-demo.sh plants it, with the real failing pytest output from a scratch copy.
PRESETS = {
    "broken-09": {
        "title": "Demo broken state 09 (held out: never in training)",
        "source": "calc/mod_09.py",
        "test": "tests/test_mod_09.py",
        "plant": ("reversed(text.split())", "text.split()"),
        "instruction": "The test tests/test_mod_09.py is failing. Fix the code so it passes.",
    }
}
_env = {}


def preset(pid):
    """`{id, title, instruction, files: [{path, text}], pytest: {command, output, exit_code}, prompt}`, built once."""
    if pid in _env:
        return _env[pid]
    import shutil
    import subprocess
    import sys
    import tempfile

    p = PRESETS[pid]
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "demo-repo"
        shutil.copytree(ROOT / "demo-repo", repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        src = repo / p["source"]
        src.write_text(src.read_text(encoding="utf-8").replace(*p["plant"]), encoding="utf-8")
        cmd = ["pytest", "-q", "-p", "no:cacheprovider", p["test"]]
        run = subprocess.run([sys.executable, "-m", *cmd], cwd=repo, capture_output=True, text=True, timeout=60)
        files = [{"path": f, "text": (repo / f).read_text(encoding="utf-8")} for f in (p["source"], p["test"])]
    out = (run.stdout + run.stderr).strip()
    listing = "\n\n".join(f"{f['path']}:\n```python\n{f['text']}```" for f in files)
    prompt = (
        f"{p['instruction']}\n\n{listing}\n\n$ {' '.join(cmd[:2] + cmd[4:])}\n```\n{out}\n```\n\n"
        f"Reply with the fixed {p['source']} in one python code block, then one line on what was wrong."
    )
    _env[pid] = {
        "id": pid,
        "title": p["title"],
        "instruction": p["instruction"],
        "files": files,
        "pytest": {"command": " ".join(cmd[:2] + cmd[4:]), "output": out, "exit_code": run.returncode},
        "prompt": prompt,
    }
    return _env[pid]


router = APIRouter()
_lock = threading.Lock()


def _budget():
    try:
        return json.loads(BUDGET_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"requests": 0, "cost_usd": 0.0}


def _reserve():
    """Count this request against the caps, or return the refusal."""
    with _lock:
        b = _budget()
        if b["requests"] >= MAX_REQUESTS:
            return "Demo budget reached, try again later."
        if b["cost_usd"] + WORST > MAX_USD:
            return "Demo budget reached, try again later."
        b["requests"] += 1
        BUDGET_PATH.write_text(json.dumps(b), encoding="utf-8")
    return None


def _spend(usd):
    with _lock:
        b = _budget()
        b["cost_usd"] = round(b["cost_usd"] + usd, 6)
        BUDGET_PATH.write_text(json.dumps(b), encoding="utf-8")


def _safe(text):
    """Error text for a public page: no key, no bearer token, capped."""
    text = str(text)
    for k in ("OPENAI_API_KEY", "RIVER_API_KEY"):
        if v := (os.environ.get(k) or "").strip():
            text = text.replace(v, "[key]")
    return re.sub(r"(sk-|rk-|Bearer\s+)[\w\-]{6,}", "[key]", text)[:200]


def _done(side, sid, request, response, usage, start, role, model):
    ms = round((time.monotonic() - start) * 1000)
    call_hooks(sid, request, response, ms, role, model)
    tokens = {
        "input_tokens": usage.get("prompt_tokens", 0),
        "cached_input_tokens": (usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens", 0
        ),
        "output_tokens": usage.get("completion_tokens", 0),
    }
    usd = metrics.cost(tokens, role)
    _spend(usd)
    return {
        "side": side,
        "type": "done",
        "model": model,
        "input_tokens": tokens["input_tokens"],
        "output_tokens": tokens["output_tokens"],
        "cost_usd": usd,
        "wall_ms": ms,
    }


async def _big(prompt, sid, put):
    request = {
        "model": BIG_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_completion_tokens": MAX_OUT,
        "reasoning_effort": "none",  # else hidden reasoning can spend all 400 tokens; OPENAI_EXTRA_BODY still wins
    }
    start = time.monotonic()
    chunks = []
    try:
        resp = await upstream.send(request)
        if resp.status_code >= 400:
            await resp.aread()
            await resp.aclose()
            raise RuntimeError(f"OpenAI answered HTTP {resp.status_code}")
        try:
            async for line in resp.aiter_lines():
                if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                    continue
                chunk = json.loads(line[5:])
                chunks.append(chunk)
                for c in chunk.get("choices") or []:
                    if text := (c.get("delta") or {}).get("content"):
                        await put({"side": "big", "type": "delta", "text": text})
        finally:
            await resp.aclose()
    except Exception as e:
        trace.emit(
            "Router → OpenAI",
            "chat-compare",
            f"error: {_safe(e)}",
            146,
            ["router", "openai"],
            ["frontier"],
            sid,
        )
        return await put(
            {
                "side": "big",
                "type": "error",
                "message": _safe(e)
                if isinstance(e, RuntimeError)
                else "The big model didn't answer.",
            }
        )
    usage = next((c["usage"] for c in reversed(chunks) if c.get("usage")), None) or {}
    done = _done("big", sid, request, chunks, usage, start, "frontier", BIG_MODEL)
    trace.emit(
        "Router → OpenAI",
        "chat-compare",
        f"200 · {BIG_MODEL} · {done['output_tokens']} out · ${done['cost_usd']}",
        146,
        ["router", "openai"],
        ["frontier"],
        sid,
    )
    await put(done)


def _river(prompt, model):
    """Your model through the backend river.py serves graduated calls with (train.RiverBackend), capped at 400 tokens."""
    rb = train.RiverBackend()
    r = rb._client().chat_complete_from_checkpoint(
        [{"role": "user", "content": prompt}],
        checkpoint_path=model,
        base_model=rb.BASE,
        max_tokens=MAX_OUT,
        temperature=0,
        chat_template_kwargs={"enable_thinking": False},  # a chat answer, not 400 tokens of "Thinking Process"
    )
    if r.status_code >= 400:
        raise RuntimeError(f"River answered HTTP {r.status_code}")
    body = json.loads(r.response_json)
    msg = body["choices"][0]["message"]
    # Qwen3.5's template opens <think> and the fine-tuned model never closes it: River files the answer under reasoning.
    text = msg.get("content") or msg.get("reasoning_content") or ""
    return text, body.get("usage") or {}


async def _small(prompt, sid, put, model):
    request = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_OUT,
    }
    start = time.monotonic()
    try:
        text, usage = await asyncio.to_thread(_river, prompt, model)
    except Exception as e:
        trace.emit(
            "Router → River",
            "chat-compare",
            f"error: {_safe(e)}",
            146,
            ["router", "river"],
            ["owned"],
            sid,
        )
        return await put(
            {
                "side": "small",
                "type": "error",
                "message": _safe(e)
                if isinstance(e, RuntimeError)
                else "Your model didn't answer.",
            }
        )
    if text:
        await put({"side": "small", "type": "delta", "text": text})
    body = {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
    }
    done = _done("small", sid, request, body, usage, start, "owned", model)
    trace.emit(
        "Router → River",
        "chat-compare",
        f"200 · {done['output_tokens']} out · ${done['cost_usd']}",
        146,
        ["router", "river"],
        ["owned"],
        sid,
    )
    await put(done)


@router.get("/api/chat-preset")
def chat_preset():
    return preset("broken-09")


@router.post("/api/chat-compare")
async def chat_compare(req: Request):
    t0 = time.monotonic()
    try:
        body = await req.json()
    except Exception:
        body = {}
    pid, free = (body.get("preset"), body.get("prompt")) if isinstance(body, dict) else (None, None)
    if pid in PRESETS:
        prompt = preset(pid)["prompt"]
    elif isinstance(free, str) and free.strip():  # a person's own question, same caps as a preset
        if len(free) > MAX_PROMPT:
            return JSONResponse({"error": f"Keep it under {MAX_PROMPT:,} characters."}, 400)
        prompt = free
    else:
        return JSONResponse({"error": "Type a question, or press Run both for the preset task."}, 400)
    t0 = time.monotonic()  # the environment is built (once); both calls launch from here
    if refusal := _reserve():
        return JSONResponse({"error": refusal}, 429)
    sid = f"chat-{uuid.uuid4().hex[:12]}"
    small = small_model()
    q = asyncio.Queue()
    # Both calls are scheduled before either runs, so they leave together.
    for side, model in (("big", BIG_MODEL), ("small", small)):
        q.put_nowait({"side": side, "type": "start", "t_ms": round((time.monotonic() - t0) * 1000), "model": model})
    tasks = [asyncio.create_task(_big(prompt, sid, q.put)), asyncio.create_task(_small(prompt, sid, q.put, small))]
    for t in tasks:
        t.add_done_callback(lambda _: q.put_nowait(None))

    async def events():
        left = len(tasks)
        while left:
            e = await q.get()
            if e is None:
                left -= 1
                continue
            yield f"data: {json.dumps(e)}\n\n"
        yield 'data: {"type": "end"}\n\n'

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"}
    )


app.include_router(router)
