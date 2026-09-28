import shutil

from conftest import ROOT, jsonl
from graduate import registry


def test_graduation_writes_graduated_md_and_fails_open(workdir, monkeypatch):
    monkeypatch.setenv("GBRAIN_BIN", str(workdir / "no-such-gbrain"))
    shutil.copy(ROOT / "registry.example.json", workdir / "registry.json")
    registry.transition("fix-lint", "GRADUATED", graduated_at="2026-09-27T16:00:00Z")
    md = (workdir / "GRADUATED.md").read_text(encoding="utf-8")
    assert "- fix-lint: graduated 2026-09-27T16:00:00Z" in md
    assert "- update-changelog:" in md and "bump-dependency" not in md
    registry.transition("update-changelog", "PROBATION")
    assert "update-changelog" not in (workdir / "GRADUATED.md").read_text()
    assert jsonl(workdir / "trace.jsonl")[-1]["result"].startswith("skipped:")
