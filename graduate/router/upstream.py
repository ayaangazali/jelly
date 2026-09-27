"""Frontier upstream client (#13).

The frontier is any OpenAI-compatible Chat Completions endpoint:
- `OPENAI_API_KEY`: the server-side key. Read from the environment, else from `.env` in the cwd.
- `OPENAI_BASE_URL`: default `https://api.openai.com/v1`. Point it at a stub to test offline.
- The model id is `OPENAI_MODEL`, else `frontier.model` in `prices.json` (else `fixtures/prices.example.json`), contracts §9.
"""

import json
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

NO_KEY = "OPENAI_API_KEY is not set or not a key: run `graduate init`, or add it to .env in the directory you run the router from."

# One shared client; agents can think for minutes, so the read timeout is long.
client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=600.0))


def clean_key(key):
    """The key stripped, or "" if a character in it (a CRLF env file's \\r) would put it in httpx's error text (#97)."""
    key = (key or "").strip()
    return key if key.isascii() and key.isprintable() else ""


async def send(body):
    """POST `body` to the frontier and return the response with its body still unread (stream it or `aread()` it).
    Without a key it answers 401 itself with the fix (#73), rather than sending `Bearer ` for httpx to reject."""
    key = clean_key(os.environ.get("OPENAI_API_KEY"))
    if not key:
        return httpx.Response(401, json={"error": {"message": NO_KEY, "type": "missing_api_key"}})
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    request = client.build_request("POST", URL, json=body, headers=headers)
    return await client.send(request, stream=True)
