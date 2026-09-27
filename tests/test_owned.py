"""The owned model (#22 trainer, #37 serving) with a fake backend: no torch, no River, no network."""

import json
import os
import subprocess
import sys
import time

import pytest

from conftest import ROOT, assert_trace, jsonl
from graduate import registry
from graduate.registrar import train

TT = "fix-failing-test"
CALL = {
    "id": "c1",
    "type": "function",
    "function": {"name": "read", "arguments": '{"filePath": "/r/calc/mod_09.py"}'},
}


class Fake:
    def __init__(self, fail=None):
        self.fail, self.seen = fail, []

    def train(self, chats, name, log, steps=None):
        if self.fail:
            raise self.fail
        for step, loss in ((1, 1.5), (2, 0.4)):
            log({"step": step, "loss": loss})
        return f"/ckpt/{name}"

    def complete(self, model, messages, tools):
        if self.fail:
            raise self.fail
        self.seen.append((model, messages))
        return {"role": "assistant", "content": "", "tool_calls": [CALL]}, {
            "prompt_tokens": 900,
            "completion_tokens": 30,
        }


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(train, "backend", lambda model=None: f)
    return f


def task(state, **fields):
    registry._write(
        {
            "task_types": {
                TT: {
                    **registry._new_task_type(TT),
                    "state": state,
                    "consent": True,
                    **fields,
                }
            },
            "events": [],
        }
    )


def test_parse_qwen_tool_calls():
    msg = train.parse(
        '<think>hm</think>Reading.<tool_call>\n{"name": "read", "arguments": {"filePath": "a.py"}}\n</tool_call>'
        "<tool_call>{broken</tool_call>"
    )
    assert msg["content"] == "Reading."
    [c] = msg["tool_calls"]
    assert c["function"] == {"name": "read", "arguments": '{"filePath": "a.py"}'}
    assert train.parse("Fixed.") == {"role": "assistant", "content": "Fixed."}


def test_compact_keeps_env_and_task_tools():
    system = (
        "You are opencode...\n" * 500
        + "<env>\n  Working directory: /r\n</env>\nmore rules"
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": "Line one.\nLine two.",
                "parameters": {},
            },
        }
        for n in ("read", "edit", "todowrite", "webfetch")
    ]
    ms, short = train.compact(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": [{"type": "text", "text": "fix it"}]},
            {"role": "assistant", "content": None, "tool_calls": [CALL]},
        ],
        tools,
    )
    assert ms[0]["content"] == train.SYSTEM + "\n<env>\n  Working directory: /r\n</env>"
    assert ms[1]["content"] == "fix it" and ms[2]["content"] == ""
    assert ms[2]["tool_calls"][0]["function"]["arguments"] == {
        "filePath": "/r/calc/mod_09.py"
    }
    assert [t["function"]["name"] for t in short] == ["read", "edit"]
    assert short[0]["function"]["description"] == "Line one."
    # §6a records carry flattened ToolSpecs: same result
    assert train.compact([], [t["function"] for t in tools])[1] == short


def test_train_graduates(workdir, fake):
    task("READY", trained_on_runs=0)
    (workdir / "data").mkdir()
    (workdir / f"data/{TT}.chat.jsonl").write_text(
        (ROOT / "fixtures/sft-chat.example.json").read_text().replace("\n", "") + "\n",
        encoding="utf-8",
    )
    assert train.run(TT) == f"/ckpt/{TT}-v1"
    tt = registry.load()["task_types"][TT]
    assert (tt["state"], tt["model"], tt["serving"], tt["trained_on_runs"]) == (
        "GRADUATED",
        f"/ckpt/{TT}-v1",
        "checkpoint",
        1,
    )
    assert tt["graduated_at"] and tt["deployment"] is None
    assert [r["loss"] for r in jsonl(workdir / f"data/{TT}.loss.jsonl")] == [1.5, 0.4]
    assert [e["kind"] for e in registry.load()["events"]] == ["graduated", "training"]
    edges = {e for ev in assert_trace() for e in ev["edges"]}
    assert {"approved", "serve", "graduate"} <= edges


def test_failed_training_goes_back_to_ready(workdir, fake):
    task("TRAINING")
    fake.fail = RuntimeError("out of memory")
    with pytest.raises(FileNotFoundError):  # no chat records at all
        train.run(TT)
    assert registry.load()["task_types"][TT]["state"] == "READY"
    task("TRAINING")
    (workdir / "data").mkdir()
    (workdir / f"data/{TT}.chat.jsonl").write_text("{}\n")
    with pytest.raises(RuntimeError):
        train.run(TT)
    assert registry.load()["task_types"][TT]["state"] == "READY"
    assert "out of memory" in registry.load()["events"][0]["text"]


def test_stale_training_resets_on_next_start(workdir):
    task("TRAINING")
    registry.add_event("training", TT, "started")
    train.reset_stale()
    assert registry.load()["task_types"][TT]["state"] == "TRAINING"  # fresh
    reg = registry.load()
    reg["events"][0]["ts"] = "2026-09-27T00:00:00Z"
    registry._write(reg)
    train.reset_stale()
    assert registry.load()["task_types"][TT]["state"] == "READY"


def test_use_checkpoint_graduates_in_under_5s(workdir):
    task("READY", trained_on_runs=8)
    (workdir / "ck").mkdir()
    (workdir / "ck/adapter_config.json").write_text("{}")
    t0 = time.monotonic()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "graduate.registrar.train",
            TT,
            "--use-checkpoint",
            "ck",
        ],
        check=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
    )
    assert time.monotonic() - t0 < 5
    tt = registry.load()["task_types"][TT]
    assert (tt["state"], tt["model"], tt["trained_on_runs"]) == (
        "GRADUATED",
        str(workdir / "ck"),
        8,
    )


def owned_call(router, fake, sid, **body):
    task("GRADUATED", model="/ckpt/x-v1", serving="checkpoint")
    router("POST", "/api/sessions", json={"session_id": sid, "task_type": TT})
    req = {
        "model": "graduate",
        "messages": [
            {"role": "user", "content": "The test tests/test_mod_09.py is failing."}
        ],
        "tools": [{"type": "function", "function": {"name": "read", "parameters": {}}}],
        **body,
    }
    return router(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {sid}"},
        json=req,
    )


def test_owned_stream_is_openai_sse_with_tool_calls(router, stub, fake, workdir):
    r = owned_call(
        router,
        fake,
        "sess-0000000000a1",
        stream=True,
        stream_options={"include_usage": True},
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith(
        "text/event-stream"
    )
    lines = [l[6:] for l in r.text.split("\n\n") if l]
    assert lines[-1] == "[DONE]"
    chunks = [json.loads(l) for l in lines[:-1]]
    assert len({c["id"] for c in chunks}) == 1 and all(
        c["object"] == "chat.completion.chunk" for c in chunks
    )
    [call] = [
        tc
        for c in chunks
        for ch in c["choices"]
        for tc in ch["delta"].get("tool_calls", [])
    ]
    assert call == {**CALL, "index": 0}
    assert chunks[-2]["choices"][0]["finish_reason"] == "tool_calls"
    assert chunks[-1]["usage"]["completion_tokens"] == 30
    assert stub.requests == [] and fake.seen[0][0] == "/ckpt/x-v1"
    [line] = jsonl(workdir / "sessions/sess-0000000000a1.jsonl")
    assert (line["upstream"], line["model"]) == ("owned", "/ckpt/x-v1")
    assert line["response"]["tool_calls"][0]["function"] == CALL["function"]
    assert any(e["edges"] == ["owned"] and e["issue"] == 37 for e in assert_trace())


def test_owned_json_and_no_usage_chunk_unless_asked(router, stub, fake):
    r = owned_call(router, fake, "sess-0000000000a2")
    body = r.json()
    assert body["object"] == "chat.completion" and body["choices"][0]["message"][
        "tool_calls"
    ] == [CALL]
    r = owned_call(router, fake, "sess-0000000000a3", stream=True)
    assert '"usage"' not in r.text


def test_owned_model_down_falls_back_to_frontier(router, stub, fake):
    fake.fail = OSError("checkpoint missing")
    r = owned_call(router, fake, "sess-0000000000a4")
    assert (
        r.status_code == 200
        and r.json()["choices"][0]["message"]["content"] == "Fixed."
    )
    assert len(stub.requests) == 1
    assert registry.load()["events"][0]["kind"] == "error"


def test_backend_choice(monkeypatch):
    monkeypatch.delenv("RIVER_API_KEY", raising=False)
    monkeypatch.delenv("GRADUATE_OWNED_BACKEND", raising=False)
    assert isinstance(train.backend(), train.LocalBackend)
    assert isinstance(train.backend("river://run/sampler_weights/x"), train.RiverBackend)
    monkeypatch.setenv("RIVER_API_KEY", "rv_x")
    assert isinstance(train.backend(), train.RiverBackend)
    assert isinstance(train.backend("/ckpt/x-v1"), train.LocalBackend)  # a local checkpoint stays local
    monkeypatch.setenv("GRADUATE_OWNED_BACKEND", "none")
    with pytest.raises(RuntimeError):
        train.backend("/ckpt/x-v1")
