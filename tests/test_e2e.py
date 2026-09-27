"""`make e2e` (#59) skip paths, offline. The cap paths need OpenCode: scripts/corpus-dryrun.sh (make e2e-replay)."""

import json
from pathlib import Path

import httpx
import pytest

from graduate import e2e

QUOTA = {"error": {"type": "insufficient_quota", "code": "insufficient_quota"}}


def test_no_key_skips_after_the_estimate(workdir, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert e2e.main() == 0
    out = capsys.readouterr().out
    assert out.index("est.   $") < out.index("skipped: no key")


@pytest.mark.parametrize(
    "status, body, code, said",
    [
        (429, QUOTA, 0, "skipped: no credit"),
        (404, {"error": {"code": "model_not_found"}}, 1, "FAIL: probe 404"),
        (429, {"error": {"code": "rate_limit_exceeded"}}, 1, "FAIL: probe 429"),
    ],
)
def test_one_1_token_probe_and_no_session_unless_it_answers(
    workdir, monkeypatch, capsys, status, body, code, said
):
    seen = []

    def frontier(request):
        seen.append(json.loads(request.content))
        return httpx.Response(status, json=body)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        e2e, "http", httpx.Client(transport=httpx.MockTransport(frontier))
    )
    assert e2e.main() == code
    assert said in capsys.readouterr().out
    assert [b["max_completion_tokens"] for b in seen] == [1]
    assert not Path("backups").exists()  # nothing ran
