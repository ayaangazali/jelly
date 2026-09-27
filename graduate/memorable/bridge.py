import json
import os
import re
import subprocess
import sys
from pathlib import Path

from graduate import trace

ALLOWED_INPUT_KEYS = ("command", "file_path", "path", "pattern", "url", "query")
SLUG = re.compile(r"procedures/[A-Za-z0-9_-]+")
_warned = set()


def _warn_once(key, msg):
    if key not in _warned:
        _warned.add(key)
        print(f"memorable: {msg}", file=sys.stderr)


def _ledger_row(session_id, ledger):
    if not ledger.exists():
        return {}
    for line in reversed(ledger.read_text().splitlines()):
        row = json.loads(line)
        if row.get("session_id") == session_id:
            return row
    return {}


def _text(content):
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""


def build_trace(session_id, verify_command, exit_code, sessions_dir=Path("sessions"), harness="opencode"):
    lines = (sessions_dir / f"{session_id}.jsonl").read_text().splitlines()
    last = json.loads(lines[-1])
    messages = last["request"]["messages"] + [last["response"]]
    prompt = next((_text(m["content"]) for m in messages if m["role"] == "user"), "")
    calls = []
    for m in messages:
        for tc in m.get("tool_calls") or []:
            fn = tc["function"]
            args = fn["arguments"]
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append({
                "name": fn["name"],
                "input": {k: args[k] for k in ALLOWED_INPUT_KEYS if k in args},
                "result": {"ok": True},
            })
    calls.append({"name": "bash", "input": {"command": verify_command}, "result": {"exit_code": exit_code}})
    return {"session_id": session_id, "harness": harness, "task_description": prompt[:200], "tool_calls": calls}


def ingest(session_id, task_type=None, verify_command=None, exit_code=None, root=Path("."), harness="opencode"):
    row = _ledger_row(session_id, root / "ledger.jsonl")
    task_type = task_type or row.get("task_type")
    verify_command = verify_command or row.get("verify_command")
    exit_code = row.get("exit_code") if exit_code is None else exit_code
    if verify_command is None or exit_code is None:
        _warn_once("no-row", f"no verify command or exit code for {session_id}; skipped")
        return None

    try:
        body = build_trace(session_id, verify_command, exit_code, root / "sessions", harness)
    except (OSError, ValueError, KeyError, IndexError) as e:
        _warn_once("trace", f"couldn't build a trace for {session_id} ({e}); skipped")
        return None

    path = root / "data" / "traces" / f"{session_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2) + "\n")

    binary = os.environ.get("MEMORABLE_BIN", "memorable")
    try:
        out = subprocess.run([binary, "ingest", str(path.resolve())], capture_output=True, text=True, timeout=60)
        output = out.stdout + out.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        _warn_once("run", f"couldn't run `{binary} ingest` ({e}); skipped")
        return None

    match = SLUG.search(output)
    if out.returncode != 0 or not match:
        _warn_once("refused", f"ingest didn't return a procedure: {output.strip()[:200]}")
        trace.emit("Runner → Memorable", f"memorable ingest {path}", f"no procedure · {output.strip()[:80]}", 36,
                   nodes=["runner", "memorable"], edges=["ingest"], session_id=session_id)
        return None

    slug = match.group(0)
    if task_type:
        slug_map = root / "data" / "slug_map.json"
        mapping = json.loads(slug_map.read_text()) if slug_map.exists() else {}
        mapping[slug] = task_type
        slug_map.write_text(json.dumps(mapping, indent=2) + "\n")
    trace.emit("Runner → Memorable", f"memorable ingest {path}", f"{slug} · {len(body['tool_calls'])} steps · verify exit {exit_code}",
               36, nodes=["runner", "memorable"], edges=["ingest"], session_id=session_id)
    return slug
