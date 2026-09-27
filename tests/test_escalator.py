import subprocess
import uuid

import pytest

from graduate import escalator, runner

PER_DAY = b'{"error": {"message": "Rate limit reached for gpt-5-mini on requests per day (RPD): Limit 50"}}'
PER_MIN = b'{"error": {"message": "Rate limit reached for gpt-5-mini on requests per min (RPM): Limit 3"}}'


@pytest.mark.parametrize(
    "fail, reruns",
    [((429, PER_DAY), False), ((401, b"{}"), False), ((429, PER_MIN), True), (None, True)],
)
def test_no_frontier_rerun_when_the_frontier_last_answered_401_or_a_daily_429(
    router, stub, workdir, monkeypatch, fail, reruns
):
    repo = workdir / "repo"
    repo.mkdir()
    (repo / "m.py").write_text("")
    for cmd in (["init", "-q"], ["add", "."], ["commit", "-qm", "base"]):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *cmd], cwd=repo, check=True)
    stub.fail = fail
    sid = "sess-" + uuid.uuid4().hex[:12]
    router("POST", "/v1/chat/completions", headers={"Authorization": f"Bearer {sid}"},
           json={"model": "graduate", "messages": [{"role": "user", "content": "fix"}]})
    rerun = {"session_id": "sess-rerun", "exit_code": 0}
    ran = []
    monkeypatch.setattr(runner, "run", lambda *a, **k: ran.append(a) or rerun)
    row = {"session_id": sid, "repo": str(repo), "task_type": "fix-failing-test", "forced_failure": True,
           "exit_code": 1, "prompt": "fix", "verify_command": "true"}
    assert escalator.escalate(row, escalator.snapshot(str(repo))) is (rerun if reruns else row)
    assert bool(ran) is reruns
