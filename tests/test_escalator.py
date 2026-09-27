import json
import subprocess
import uuid

import pytest

from conftest import jsonl
from graduate import escalator, runner


def openai_429(message, type_, code):
    body = {"error": {"message": message, "type": type_, "param": None, "code": code}}
    return 429, json.dumps(body, indent=4).encode()


def limit(window):
    return openai_429(
        f"Rate limit reached for gpt-5-mini in organization org-3nOBq7XyZ on {window}: Limit 50, Used 50, "
        "Requested 1. Please try again in 28m48s. Visit https://platform.openai.com/account/rate-limits to learn more.",
        "requests",
        "rate_limit_exceeded",
    )


TOO_LARGE = openai_429(
    "Request too large for gpt-5.6-terra in organization org-3nOBq7XyZ on tokens per min (TPM): Limit 10000, "
    "Requested 10970. The input or output tokens must be reduced in order to run successfully.",
    "tokens",
    "rate_limit_exceeded",
)
NO_QUOTA = openai_429(
    "You exceeded your current quota, please check your plan and billing details. For more information on this "
    "error, read the docs: https://platform.openai.com/docs/guides/error-codes/api-errors.",
    "insufficient_quota",
    "insufficient_quota",
)
OVERLOADED = openai_429("The engine is currently overloaded, please try again later.", "server_error", None)


@pytest.fixture
def escalate(router, stub, workdir, monkeypatch):
    repo = workdir / "repo"
    repo.mkdir()
    (repo / "m.py").write_text("")
    for cmd in (["init", "-q"], ["add", "."], ["commit", "-qm", "base"]):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *cmd], cwd=repo, check=True)
    ran = []
    monkeypatch.setattr(runner, "run", lambda *a, **k: ran.append(a) or {"session_id": "sess-rerun", "exit_code": 0})

    def call(fail):
        stub.fail = fail
        sid = "sess-" + uuid.uuid4().hex[:12]
        router("POST", "/v1/chat/completions", headers={"Authorization": f"Bearer {sid}"},
               json={"model": "graduate", "messages": [{"role": "user", "content": "fix"}]})
        return sid

    def run(sid):
        row = {"session_id": sid, "repo": str(repo), "task_type": "fix-failing-test", "forced_failure": True,
               "exit_code": 1, "prompt": "fix", "verify_command": "true"}
        before = len(ran)
        escalator.escalate(row, escalator.snapshot(str(repo)))
        return len(ran) > before

    return call, run


@pytest.mark.parametrize(
    "fail, reruns",
    [
        (limit("requests per day (RPD)"), False),
        (limit("tokens per day (TPD)"), False),
        (TOO_LARGE, False),
        (NO_QUOTA, False),
        ((401, b"{}"), False),
        (limit("requests per min (RPM)"), True),
        (limit("tokens per min (TPM)"), True),
        (OVERLOADED, True),
        ((429, b""), True),
        (None, True),
    ],
)
def test_no_frontier_rerun_only_on_a_permanent_frontier_failure(escalate, fail, reruns):
    call, run = escalate
    assert run(call(fail)) is reruns


def test_a_dead_signal_older_than_an_hour_reruns_and_the_org_id_never_reaches_the_trace(escalate, workdir):
    call, run = escalate
    sid = call(limit("requests per day (RPD)"))
    events = jsonl("trace.jsonl")
    assert "org-3nOBq7XyZ" not in (workdir / "trace.jsonl").read_text() and "org-…" in events[-1]["result"]
    events[-1]["ts"] = "2026-01-01T00:00:00Z"
    (workdir / "trace.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    assert run(sid)
