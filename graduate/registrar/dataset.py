"""SFT chat and wire records (#21). Shape: graduate/contracts.md §6.

python -m graduate.registrar.dataset <task_type>            build data/<task_type>.{chat,tok,neg}.jsonl
python -m graduate.registrar.dataset <task_type> --summary  same, then print what the consent screen (#25) shows
python -m graduate.registrar.dataset --check                offline self-check on fixtures/
"""

import json
import sys
from pathlib import Path

from graduate import ledger, trace

SESSIONS_DIR = Path("sessions")  # written by graduate/router/sessionlog.py (#35)
DATA_DIR = Path("data")
BASE_MODEL = "Qwen/Qwen3.6-35B-A3B-FP8"
CTX = 32768  # ponytail: fixed cap well under the 262k window; raise if sessions get truncated
META = ("task_type", "session_id", "verify_command", "exit_code", "turns", "tool_calls")


def renderer(tokenizer=None):
    """The one place the chat template is chosen. #3 must confirm on a real key:
    BASE_MODEL is one our account can train, and the server takes the flat
    {input_ids, attention_mask, weights} form that wire() sends."""
    from river_client.renderers import (
        get_renderer,
    )  # optional extra: pip install -e '.[train]'

    return get_renderer(BASE_MODEL, tokenizer=tokenizer)


def chat_record(row, negative=False):
    """§6a: the session's last request plus its final response."""
    path = SESSIONS_DIR / f"{row['session_id']}.jsonl"
    last = json.loads(path.read_text(encoding="utf-8").strip().splitlines()[-1])
    reply = {k: v for k, v in last["response"].items() if k != "finish_reason"}
    tools = [t["function"] for t in last["request"].get("tools") or []]
    meta = {k: row[k] for k in META} | ({"negative": True} if negative else {})
    return {
        "messages": last["request"]["messages"] + [reply],
        "tools": [
            {
                "name": f["name"],
                "description": f.get("description", ""),
                "parameters": f.get("parameters", {}),
            }
            for f in tools
        ],
        "metadata": meta,
    }


def wire(r, record):
    """§6b: River's renderer, every assistant turn trained. Returns (wire, truncated)."""
    from river_client.renderers import TrainingExample, TrainOnWhat

    ex = r.build_training_example(
        record["messages"], tools=record["tools"], train_on=TrainOnWhat.ALL_ASSISTANT
    )
    # Qwen3.5+ renderers also attach a chunked model_input, which to_dict() would emit
    # instead of input_ids; text-only sessions take the flat form (contracts §6b, consent #25).
    flat = TrainingExample(ex.input_ids[:CTX], ex.weights[:CTX])
    return flat.to_dict(), len(ex.input_ids) > CTX


def build(task_type, tokenizer=None):
    rows = [r for r in ledger.rows() if r["task_type"] == task_type]
    passing = [
        r
        for r in rows
        if r["routed_to"] == "frontier"
        and r["exit_code"] == 0
        and r["escalated_from"] is None
    ]
    failed = [
        r
        for r in rows
        if r["routed_to"] == "owned"
        and r["exit_code"] != 0
        and not r.get("forced_failure")
    ]
    chats, negs, skipped = [], [], 0
    for rs, out, negative in ((passing, chats, False), (failed, negs, True)):
        for r in rs:
            try:
                out.append(chat_record(r, negative))
            except (FileNotFoundError, IndexError):  # no session log, or an empty one
                skipped += 1
    rend = renderer(tokenizer) if chats else None
    wires = [wire(rend, c) for c in chats]
    DATA_DIR.mkdir(exist_ok=True)
    for suffix, recs in (
        ("chat", chats),
        ("tok", [w for w, _ in wires]),
        ("neg", negs),
    ):
        (DATA_DIR / f"{task_type}.{suffix}.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in recs), encoding="utf-8"
        )
    summary = {
        "task_type": task_type,
        "records": len(chats),
        "tokens": sum(len(w["input_ids"]) for w, _ in wires),
        "truncated": sum(t for _, t in wires),
        "skipped": skipped,
        "negatives": len(negs),
        "sample": chats[0] if chats else None,
    }
    trace.emit(
        "Registrar",
        f"dataset.py: {len(passing)} passing sessions from {SESSIONS_DIR}/*.jsonl",
        f"{summary['records']} records · {summary['tokens']} tokens → {DATA_DIR}/{task_type}.tok.jsonl",
        21,
        ["registrar", "disk"],
        [],
    )
    return summary


class _CharTokenizer:
    """Offline stand-in for the HF tokenizer: one id per character, so ids decode back to text."""

    def encode(self, text, add_special_tokens=False):
        return [ord(c) for c in text]

    def convert_tokens_to_ids(self, token):
        return 0


def _check():
    import os
    import shutil
    import tempfile

    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    chat = json.loads((fixtures / "sft-chat.example.json").read_text())
    session = (fixtures / "session.example.jsonl").read_text().splitlines()
    rows = [
        json.loads(l)
        for l in (fixtures / "ledger.example.jsonl").read_text().splitlines()
    ]
    os.chdir(tempfile.mkdtemp())
    SESSIONS_DIR.mkdir()
    for r in rows:  # every ledger session replays the fixture conversation
        (SESSIONS_DIR / f"{r['session_id']}.jsonl").write_text(
            "".join(
                json.dumps(json.loads(l) | {"session_id": r["session_id"]}) + "\n"
                for l in session
            )
        )
    # A second clean pass counts; the fixture's escalation rerun (c5f2), a faked
    # failure and a lost log never become data.
    rows += [
        rows[0] | {"session_id": "sess-000000000001"},
        rows[2] | {"session_id": "sess-000000000002", "forced_failure": True},
        rows[0] | {"session_id": "sess-00000000dead"},
    ]
    shutil.copy(
        SESSIONS_DIR / "sess-4d2e81a09f3c.jsonl",
        SESSIONS_DIR / "sess-000000000001.jsonl",
    )
    shutil.copy(
        SESSIONS_DIR / "sess-a91e7f0c55b2.jsonl",
        SESSIONS_DIR / "sess-000000000002.jsonl",
    )
    Path(ledger.LEDGER_PATH).write_text("".join(json.dumps(r) + "\n" for r in rows))

    s = build("fix-failing-test", tokenizer=_CharTokenizer())
    read = lambda sfx: [
        json.loads(l)
        for l in (DATA_DIR / f"fix-failing-test.{sfx}.jsonl").read_text().splitlines()
    ]
    chats, toks, negs = read("chat"), read("tok"), read("neg")

    # One chat and one wire record per passing frontier session, equal to the §6a fixture.
    assert [c["metadata"]["session_id"] for c in chats] == [
        "sess-4d2e81a09f3c",
        "sess-000000000001",
    ]
    assert (
        chats[0]["messages"] == chat["messages"] and chats[0]["tools"] == chat["tools"]
    )
    assert chats[0]["metadata"] == {k: rows[0][k] for k in META}
    assert [n["metadata"] for n in negs] == [
        {k: rows[2][k] for k in META} | {"negative": True}
    ]
    assert (s["records"], s["negatives"], s["skipped"], s["truncated"]) == (2, 1, 1, 0)
    assert (
        s["tokens"] == sum(len(t["input_ids"]) for t in toks)
        and s["sample"] == chats[0]
    )

    # Equal lengths, weights normalized, and every weighted position predicts an assistant token.
    for t in toks:
        assert set(t) == {"input_ids", "attention_mask", "weights"}
        assert len(t["input_ids"]) == len(t["attention_mask"]) == len(t["weights"])
        assert set(t["attention_mask"]) == {1} and abs(sum(t["weights"]) - 1) < 1e-9
        trained = "".join(
            chr(t["input_ids"][i + 1]) for i, w in enumerate(t["weights"]) if w
        )
        for said in (
            "Fixed: add() subtracted instead of adding.",
            "calc/mod_05.py",
            "pytest -q tests/test_mod_05.py",
        ):
            assert said in trained, said
        for heard in (
            "You are a coding agent",
            "is failing. Fix the code",
            "1 passed in 0.04s",
            "Edited calc/mod_05.py",
            "Read a file",
        ):
            assert heard not in trained, heard

    # Truncation is counted, not silent.
    global CTX
    CTX = 50
    assert build("fix-failing-test", tokenizer=_CharTokenizer())["truncated"] == 2
    assert {len(t["input_ids"]) for t in read("tok")} == {50}
    print("dataset self-check ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        _check()
    elif len(sys.argv) > 1:
        s = build(sys.argv[1])
        if "--summary" in sys.argv:
            print(json.dumps(s, indent=2))
        else:
            print(
                f"{s['task_type']}: {s['records']} records, {s['tokens']} tokens "
                f"({s['truncated']} truncated, {s['skipped']} skipped, {s['negatives']} negative) → {DATA_DIR}/"
            )
    else:
        sys.exit(__doc__)
