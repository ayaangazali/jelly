"""Shared fixtures: an offline OpenAI-compatible frontier stub, a scratch working directory, contract checks."""

import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest

from graduate.router import upstream

ROOT = Path(__file__).resolve().parents[1]
SERVER_KEY = "sk-stub-server"
USAGE = {
    "prompt_tokens": 1400,
    "completion_tokens": 60,
    "prompt_tokens_details": {"cached_tokens": 1280},
}
TOOL_CALLS = [
    {
        "id": "call_1",
        "type": "function",
        "function": {"name": "read", "arguments": '{"file_path": "calc/mod_05.py"}'},
    },
    {
        "id": "call_2",
        "type": "function",
        "function": {"name": "bash", "arguments": '{"command": "pytest -q"}'},
    },
]


@pytest.fixture(autouse=True)
def offline_memorable(monkeypatch):
    monkeypatch.setenv("MEMORABLE_BIN", "false")


def example(name):
    """The first record of an example file under the repo root, e.g. `fixtures/metrics.example.jsonl`."""
    text = (ROOT / name).read_text(encoding="utf-8")
    return json.loads(text.splitlines()[0] if name.endswith(".jsonl") else text)


def jsonl(path):
    return [
        json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
    ]


def _kind(v):
    return (
        "number"
        if isinstance(v, (int, float)) and not isinstance(v, bool)
        else type(v).__name__
    )


def assert_shape(got, want):
    """Contract check: the example's fields, in its order, each with its JSON type (null on either side matches)."""
    assert list(got) == list(want)
    bad = {
        k: (got[k], v)
        for k, v in want.items()
        if None not in (got[k], v) and _kind(got[k]) != _kind(v)
    }
    assert not bad, bad


def assert_trace():
    """Every trace event has the §8 shape and only node/edge ids the dashboard knows."""
    lines = (ROOT / "graduate/contracts.md").read_text(encoding="utf-8").splitlines()
    ids = {
        k: set(re.findall(r"`(\w+)`", next(l for l in lines if l.startswith(k))))
        for k in ("Node ids", "Edge ids")
    }
    events = jsonl("trace.jsonl")
    for e in events:
        assert_shape(e, example("fixtures/trace.example.jsonl"))
        assert (
            set(e["nodes"]) <= ids["Node ids"] and set(e["edges"]) <= ids["Edge ids"]
        ), e
    return events


class StubUpstream:
    """The frontier, as an httpx transport: no port, no network, no key.

    Non-stream calls get one JSON body; `stream: true` calls get SSE chunks, one per network piece, with usage in the
    last chunk. `tools = True` answers with two parallel tool calls whose argument deltas interleave. `fail` set to
    `(status, body_bytes)` answers every call with that error; set to an httpx exception, the frontier is unreachable.
    `requests` holds every `(headers, body)` the frontier received.
    """

    def __init__(self):
        self.requests, self.tools, self.fail = [], False, None

    def message(self):
        """The assistant message a client should end up with, streamed or not."""
        if self.tools:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": TOOL_CALLS,
                "finish_reason": "tool_calls",
            }
        return {"role": "assistant", "content": "Fixed.", "finish_reason": "stop"}

    def body(self):
        m = dict(self.message())
        finish = m.pop("finish_reason")
        return json.dumps(  # indented, so a router that re-serializes fails the byte-for-byte check
            {
                "id": "chatcmpl-stub",
                "object": "chat.completion",
                "created": 0,
                "model": "stub",
                "choices": [{"index": 0, "message": m, "finish_reason": finish}],
                "usage": USAGE,
            },
            indent=1,
        ).encode()

    def chunks(self):
        if self.tools:

            def tc(
                i, args, name=None, **first
            ):  # a call's first delta has id, type, name
                fn = {"name": name, "arguments": args} if name else {"arguments": args}
                return {"tool_calls": [{"index": i, **first, "function": fn}]}

            deltas = [
                {"role": "assistant", "content": None},
                tc(0, "", id="call_1", type="function", name="read"),
                tc(0, '{"file_path": '),
                tc(
                    1, "", id="call_2", type="function", name="bash"
                ),  # before call_1 ends
                tc(0, '"calc/mod_05.py"}'),
                tc(1, '{"command": "pytest -q"}'),
            ]
        else:
            deltas = [
                {"role": "assistant", "content": ""},
                {"content": "Fi"},
                {"content": "xed."},
            ]
        deltas.append({})
        base = {
            "id": "chatcmpl-stub",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "stub",
        }
        out = [
            dict(base, choices=[{"index": 0, "delta": d, "finish_reason": None}])
            for d in deltas
        ]
        out[-1]["choices"][0]["finish_reason"] = self.message()["finish_reason"]
        return out + [dict(base, choices=[], usage=USAGE)]

    def sse(self):
        return [f"data: {json.dumps(c)}\n\n".encode() for c in self.chunks()] + [
            b"data: [DONE]\n\n"
        ]

    async def handle(self, request):
        body = json.loads(request.content)
        self.requests.append((request.headers, body))
        if isinstance(self.fail, Exception):
            raise self.fail
        if self.fail:
            status, content = self.fail
            return httpx.Response(
                status, content=content, headers={"content-type": "application/json"}
            )
        if not body.get("stream"):
            return httpx.Response(
                200, content=self.body(), headers={"content-type": "application/json"}
            )

        async def pieces():
            for piece in self.sse():
                yield piece

        return httpx.Response(
            200, content=pieces(), headers={"content-type": "text/event-stream"}
        )


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Scratch cwd: metrics.jsonl, sessions/, ledger.jsonl, registry.json and trace.jsonl land here, never in the repo."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def stub(workdir, monkeypatch):
    s = StubUpstream()
    monkeypatch.setenv("OPENAI_API_KEY", SERVER_KEY)
    monkeypatch.setattr(
        upstream, "client", httpx.AsyncClient(transport=httpx.MockTransport(s.handle))
    )
    return s


@pytest.fixture
def router(stub):
    """Call the whole router app in-process (every plug-in loaded), with the stub as its frontier."""
    from graduate.router.app import app

    async def request(method, path, **kw):
        transport = httpx.ASGITransport(app=app)  # returns after background hooks ran
        async with httpx.AsyncClient(transport=transport, base_url="http://router") as c:
            return await c.request(method, path, **kw)

    return lambda method, path, **kw: asyncio.run(request(method, path, **kw))
