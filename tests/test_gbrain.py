import json
import shutil

from conftest import ROOT, jsonl
from graduate import gbrain, registry


def test_graduation_writes_graduated_md_and_fails_open(workdir, monkeypatch):
    monkeypatch.setenv("GBRAIN_BIN", str(workdir / "no-such-gbrain"))
    shutil.copy(ROOT / "registry.example.json", workdir / "registry.json")
    registry.transition("fix-lint", "GRADUATED", graduated_at="2026-09-27T16:00:00Z")
    md = (workdir / "GRADUATED.md").read_text(encoding="utf-8")
    assert "## fix-lint\n- checkpoint: none recorded\n- verified runs: " in md and "- graduated: 2026-09-27T16:00:00Z" in md
    assert "## update-changelog\n- checkpoint: river://run-4c1e/sampler_weights/update-changelog-v1\n" in md
    assert "bump-dependency" not in md
    registry.transition("update-changelog", "PROBATION")
    assert "update-changelog" not in (workdir / "GRADUATED.md").read_text()
    assert jsonl(workdir / "trace.jsonl")[-1]["result"].startswith("skipped:")


def test_graduation_survives_a_malformed_registry_entry(workdir):
    shutil.copy(ROOT / "registry.example.json", workdir / "registry.json")
    reg = registry.load()
    del reg["task_types"]["update-changelog"]["graduated_at"]
    (workdir / "registry.json").write_text(json.dumps(reg))
    assert registry.transition("fix-lint", "GRADUATED")["state"] == "GRADUATED"
    assert jsonl(workdir / "trace.jsonl")[-1]["result"].startswith("skipped:")


def test_nothing_graduated_says_so_in_one_line():
    tts = {"fix-failing-test": {"state": "READY", "verified_runs": 8}}
    assert gbrain.render(tts) == "# Graduated task types\n\nNothing has graduated yet (fix-failing-test is READY with 8 verified runs).\n"
    assert gbrain.render({}) == "# Graduated task types\n\nNothing has graduated yet.\n"
