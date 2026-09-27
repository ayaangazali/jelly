import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import river_client

ROOT = Path(__file__).resolve().parent.parent
PREFERRED = ["qwen3.6-35b-a3b", "qwen3.5-9b", "nemotron-3.5-lightning-30b-a3b"]


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() and not key.lstrip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def pick_model(capabilities):
    wanted = os.environ.get("RIVER_BASE_MODEL")
    if wanted:
        return wanted
    lowered = {c.lower(): c for c in capabilities}
    for prefix in PREFERRED:
        for low, original in lowered.items():
            if low.startswith(prefix):
                return original
    return capabilities[0] if capabilities else None


def main():
    load_env()
    key = os.environ.get("RIVER_API_KEY", "")
    if not key.startswith("rv_"):
        sys.exit("RIVER_API_KEY is missing or doesn't start with rv_. Put it in .env (see .env.example).")

    client = river_client.Client(api_key=key)
    started = time.monotonic()
    capabilities = client.get_capabilities()
    caps_ms = round((time.monotonic() - started) * 1000)

    model = pick_model(capabilities)
    if not model:
        sys.exit("get_capabilities() returned no models for this key. Ask River on Discord which models the key should see.")

    messages = [{"role": "user", "content": "Reply with exactly one word: ready"}]
    started = time.monotonic()
    result = client.chat_complete(messages, base_model=model)
    call_ms = round((time.monotonic() - started) * 1000)

    report = {
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "river_client_version": getattr(river_client, "__version__", None) or _dist_version(),
        "capabilities": capabilities,
        "capabilities_ms": caps_ms,
        "chosen_base_model": model,
        "chat_complete": {
            "request": {"messages": messages, "base_model": model},
            "status_code": result.status_code,
            "response_json": result.response_json,
            "latency_ms": call_ms,
        },
    }
    out = ROOT / "docs" / "river-check.json"
    out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"{len(capabilities)} models visible. Chose {model}. chat_complete -> {result.status_code} in {call_ms} ms.")
    print(f"Wrote {out.relative_to(ROOT)}")


def _dist_version():
    from importlib.metadata import version

    return version("river-client")


if __name__ == "__main__":
    try:
        main()
    except river_client.RiverError as e:
        sys.exit(f"River: {e}")
