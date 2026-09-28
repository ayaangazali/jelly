"""What the watcher and registry write, checked against registry.example.json and contracts §1 and §5."""

import shutil

from conftest import ROOT, assert_shape, assert_trace, example
from graduate import registry, watcher


def test_watcher_writes_registry_in_contract_shape(workdir, monkeypatch):
    monkeypatch.setattr(
        registry, "GRADUATE_N", 1
    )  # the fixture ledger has 1 verified frontier run
    shutil.copy(ROOT / "fixtures/ledger.example.jsonl", "ledger.jsonl")
    watcher.scan()

    reg, want = registry.load(), example("registry.example.json")
    assert list(reg) == list(want)
    tt = reg["task_types"]["fix-failing-test"]
    assert_shape(tt, want["task_types"]["fix-failing-test"])
    assert_shape(tt["baseline"], want["task_types"]["fix-failing-test"]["baseline"])
    assert (tt["state"], tt["verified_runs"], tt["failed_runs"]) == ("READY", 1, 0)
    [event] = reg["events"]
    assert_shape(event, want["events"][0])
    assert event["kind"] == "ready"
    assert_trace()


def test_registry_example_uses_contract_states():
    reg = example("registry.example.json")
    states = {s for pair in registry.LEGAL for s in pair}
    assert {
        tt["state"] for tt in reg["task_types"].values()
    } == states  # one task type in every state
    assert {e["kind"] for e in reg["events"]} <= registry.EVENT_KINDS


def test_sft_chat_record_matches_fixture(workdir):
    """§6a without River: a passing session's log becomes the sft-chat.example.json record."""
    from graduate.registrar import dataset

    row = example("fixtures/ledger.example.jsonl")
    (workdir / "sessions").mkdir()
    lines = (ROOT / "fixtures/session.example.jsonl").read_text().splitlines()
    (workdir / f"sessions/{row['session_id']}.jsonl").write_text("\n".join(lines))
    want = example("fixtures/sft-chat.example.json")
    got = dataset.chat_record(row)
    assert_shape(got, want)
    assert (got["messages"], got["tools"]) == (want["messages"], want["tools"])
    assert_shape(got["metadata"], want["metadata"])
