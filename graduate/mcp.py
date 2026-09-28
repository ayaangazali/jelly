import json
import sys

from graduate import registry
from graduate.router.state import build_state, jsonl, totals

COUNTS = ("state", "verified_runs", "failed_runs", "verified_since_graduation", "failures_since_graduation")
TOOLS = [
    {
        "name": "graduate.status",
        "description": "Every task type with its graduation state and run counts, as GET /state reports them.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "graduate.savings",
        "description": "Owned runs and USD saved against the frontier baseline, as /state totals; `since` (ISO 8601) keeps ledger rows started at or after it.",
        "inputSchema": {"type": "object", "properties": {"since": {"type": "string"}}},
    },
]


def status():
    s = build_state()
    types = s["registry"].get("task_types", {})
    return {"config": s["config"], "task_types": {k: {f: t.get(f) for f in COUNTS} for k, t in types.items()}}


def savings(since=None):
    ledger = [r for r in jsonl("ledger.jsonl", 10_000) if not since or r.get("started_at", "") >= since]
    return totals(registry.load().get("task_types", {}), ledger)


def handle(msg):
    method, params = msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "graduate", "version": "0.1.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        fn = {"graduate.status": status, "graduate.savings": savings}.get(params.get("name"))
        if fn is None:
            raise LookupError(f"unknown tool {params.get('name')!r}")
        return {"content": [{"type": "text", "text": json.dumps(fn(**(params.get("arguments") or {})))}]}
    raise NotImplementedError(method)


def reply(id, **out):
    print(json.dumps({"jsonrpc": "2.0", "id": id, **out}), flush=True)


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply(None, error={"code": -32700, "message": "parse error"})
            continue
        if not isinstance(msg, dict):
            reply(None, error={"code": -32600, "message": "invalid request"})
            continue
        if "id" not in msg:
            continue
        try:
            reply(msg["id"], result=handle(msg))
        except NotImplementedError as e:
            reply(msg["id"], error={"code": -32601, "message": f"method not found: {e}"})
        except Exception as e:
            reply(msg["id"], error={"code": -32603, "message": str(e)})


if __name__ == "__main__":
    main()
