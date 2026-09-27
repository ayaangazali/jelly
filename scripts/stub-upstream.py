"""Scripted OpenAI stand-in for offline dry runs: python3 scripts/stub-upstream.py PORT AUTH_LOG

Plays one agent that fixes a demo-repo broken state in three streamed turns: `read` the module, `edit` the
planted line back (the swap comes from scripts/reset-demo.sh), then say "Fixed.". A call without tools (OpenCode's
title call) gets a one-word answer. Every request's Authorization header is appended to AUTH_LOG.
"""

import json
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUGS = {
    n: (old, new)
    for n, old, new in re.findall(
        r"(\d\d)\) old='(.*)' new='(.*)' ;;",
        (ROOT / "scripts/reset-demo.sh").read_text(),
    )
}
PORT, AUTH_LOG = int(sys.argv[1]), sys.argv[2]


def turn(body):
    """(text, tool_call) for the next assistant message."""
    if not body.get("tools"):
        return "Fix failing test", None
    msgs = json.dumps(body["messages"])
    n = re.search(r"test_mod_(\d\d)", msgs).group(1)
    # The repo OpenCode runs in (a `graduate swarm` agent's own copy), else the checkout's demo-repo.
    repo = re.search(r"Working directory: ([^\\\s\"]+)", msgs)
    path = str(Path(repo.group(1) if repo else ROOT / "demo-repo") / f"calc/mod_{n}.py")
    done = sum(m["role"] == "tool" for m in body["messages"])
    if done == 0:
        return "", ("read", {"filePath": path})
    if done == 1:
        old, new = BUGS[n]
        return "", ("edit", {"filePath": path, "oldString": new, "newString": old})
    return "Fixed.", None


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        with open(AUTH_LOG, "a") as f:
            f.write(self.headers.get("authorization", "") + "\n")
        text, call = turn(body)
        delta = {"role": "assistant", "content": text}
        if call:
            fn = {"name": call[0], "arguments": json.dumps(call[1])}
            delta["tool_calls"] = [
                {
                    "index": 0,
                    "id": f"call_{time.time_ns()}",
                    "type": "function",
                    "function": fn,
                }
            ]
        chunks = [{"choices": [{"index": 0, "delta": delta}]}]
        chunks.append(
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "tool_calls" if call else "stop",
                    }
                ]
            }
        )
        chunks.append(
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 25000,
                    "completion_tokens": 40,
                    "prompt_tokens_details": {"cached_tokens": 20000},
                },
            }
        )
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        for c in chunks:
            self.wfile.write(f"data: {json.dumps(c)}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *a):
        pass


ThreadingHTTPServer(("127.0.0.1", PORT), Stub).serve_forever()
