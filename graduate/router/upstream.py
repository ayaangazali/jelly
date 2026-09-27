"""Frontier upstream client (#13).

The frontier is any OpenAI-compatible Chat Completions endpoint:
- `OPENAI_API_KEY`: the server-side key. Read from the environment, else from `.env` in the cwd.
- `OPENAI_BASE_URL`: default `https://api.openai.com/v1`. Point it at a stub to test offline.
- The model id is `OPENAI_MODEL`, else `frontier.model` in `prices.json` (else `fixtures/prices.example.json`), contracts §9.
- `OPENAI_EXTRA_BODY`: a JSON object merged over every frontier request body, e.g.
  `{"service_tier":"priority","reasoning_effort":"none"}` (fast mode; GPT-5.x after gpt-5 reject tools beside an effort).
"""

import json
import logging
import os
from pathlib import Path

import httpx

if Path(".env").exists():
    for line in Path(".env").read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))

BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
URL = BASE_URL + "/chat/completions"
_prices = (
    Path("prices.json")
    if Path("prices.json").exists()
    else Path(__file__).parents[2] / "fixtures/prices.example.json"
)
MODEL = (
    os.environ.get("OPENAI_MODEL")
    or json.loads(_prices.read_text())["frontier"]["model"]
)
LIST_PRICES = {
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.0},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.0},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.4},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.5},
    "claude-haiku-4-5": {"input": 1.0, "cached_input": 0.1, "output": 5.0},
    "gpt-4.1": {"input": 2.0, "cached_input": 0.5, "output": 8.0},
    "gpt-4.1-mini": {"input": 0.4, "cached_input": 0.1, "output": 1.6},
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.6},
}

NO_KEY = "OPENAI_API_KEY is not set or not a key: run `graduate init`, or add it to .env in the directory you run the router from."

# One shared client; agents can think for minutes, so the read timeout is long.
client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=600.0))


def clean_key(key):
    """The key stripped, or "" if a character in it (a CRLF env file's \\r) would put it in httpx's error text (#97)."""
    key = (key or "").strip()
    return key if key.isascii() and key.isprintable() else ""


def _extra_body():
    try:
        extra = json.loads(os.environ.get("OPENAI_EXTRA_BODY") or "{}")
    except ValueError:
        extra = None
    if isinstance(extra, dict):
        return extra
    logging.getLogger("uvicorn.error").warning("OPENAI_EXTRA_BODY is not a JSON object; sending the request without it")
    return {}


async def send(body):
    """POST `body` to the frontier and return the response with its body still unread (stream it or `aread()` it).
    Without a key it answers 401 itself with the fix (#73), rather than sending `Bearer ` for httpx to reject."""
    key = clean_key(os.environ.get("OPENAI_API_KEY"))
    if not key:
        return httpx.Response(
            401, json={"error": {"message": NO_KEY, "type": "missing_api_key"}}
        )
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    # GPT-5 models reject OpenCode's `max_tokens`; every current chat model accepts this (#115).
    if "max_tokens" in body:
        body = dict(body)
        body.setdefault("max_completion_tokens", body.pop("max_tokens"))
    if extra := _extra_body():
        body = {**body, **extra}
    request = client.build_request("POST", URL, json=body, headers=headers)
    return await client.send(request, stream=True)
