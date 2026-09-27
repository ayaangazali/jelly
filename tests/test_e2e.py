"""`make e2e` (#59) skip paths, offline. The cap paths need OpenCode: scripts/corpus-dryrun.sh (make e2e-replay)."""

import json
from pathlib import Path

import httpx

from graduate import e2e


def test_no_key_skips_after_the_estimate(workdir, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert e2e.main() == 0
    out = capsys.readouterr().out
    assert out.index("est.   $") < out.index("skipped: no key")


def test_no_credit_skips_after_one_1_token_probe(workdir, monkeypatch, capsys):
    seen = []

    def frontier(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            429,
            json={
                "error": {"type": "insufficient_quota", "code": "insufficient_quota"}
            },
        )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        e2e, "http", httpx.Client(transport=httpx.MockTransport(frontier))
    )
    assert e2e.main() == 0
    assert "skipped: no credit" in capsys.readouterr().out
    assert [b["max_completion_tokens"] for b in seen] == [1]
    assert not Path("backups").exists()  # nothing ran
