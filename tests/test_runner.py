"""`graduate run` verify path with a fake agent in a scratch git repo. No router: the runner fails open."""

import re
import subprocess
import sys

import pytest

from conftest import assert_shape, assert_trace, example, jsonl
from graduate import runner

VERIFY = f"{sys.executable} -m pytest -q -p no:cacheprovider tests"
AGENT = '#!/bin/sh\necho "agent in $PWD as $GRADUATE_SESSION"\n{}\n'


@pytest.fixture
def repo(workdir, monkeypatch):
    repo = workdir / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (repo / "tests/test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    for cmd in (["init", "-q"], ["add", "."], ["commit", "-qm", "broken"]):
        subprocess.run(git + cmd, cwd=repo, check=True, capture_output=True)
    monkeypatch.setattr(runner, "ROUTER", "http://127.0.0.1:9")  # nothing listens
    return repo


@pytest.mark.parametrize(
    "action, exit_code, passed",
    [
        ("perl -pi -e 's/a - b/a + b/' calc.py", 0, 1),  # the agent fixes it
        ("true", 1, 0),  # the agent does nothing
        (
            "exec sleep 30",
            124,
            0,
        ),  # the agent hangs: killed at the timeout, still verified
    ],
)
def test_run_verifies_and_appends_one_ledger_row(
    repo, workdir, monkeypatch, action, exit_code, passed
):
    agent = workdir / "agent"
    agent.write_text(AGENT.format(action))
    agent.chmod(0o755)
    monkeypatch.setattr(runner, "OPENCODE", str(agent))
    ingested = []
    monkeypatch.setattr(runner.memorable, "ingest", lambda *a: ingested.append(a) or "procedures/abc-fix-calc")

    row = runner.run("Fix calc.", VERIFY, str(repo), timeout=1)

    assert jsonl("ledger.jsonl") == [row]
    assert_shape(row, example("fixtures/ledger.example.jsonl"))
    sid = row["session_id"]
    assert re.fullmatch(r"sess-[0-9a-f]{12}", sid)
    assert (row["exit_code"], row["tests_passed"], row["tests_total"]) == (
        exit_code,
        passed,
        1,
    )
    assert ingested == ([(row["session_id"], "unknown", VERIFY, 0)] if exit_code == 0 else [])
    assert row["procedure_slug"] == ("procedures/abc-fix-calc" if exit_code == 0 else None)
    assert (row["routed_to"], row["task_type"], row["escalated_from"], row["tampered"]) == (
        "frontier",
        "unknown",
        None,
        False,
    )
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert row["start_commit"] == head.stdout.strip()
    # The agent ran in the task repo with the session id the router reads as its bearer.
    assert f"[{sid}] agent in {repo} as {sid}" in (workdir / "terminal.log").read_text()
    assert [e["who"] for e in assert_trace()] == [
        "Runner → OpenCode",
        "Runner → Test suite",
        "Runner → Ledger",
    ]


@pytest.mark.parametrize(
    "action",
    [
        "perl -pi -e 's/add\\(2, 3\\) == 5/True/' tests/test_calc.py",
        "perl -pi -e 's/^def/import pytest\\n\\@pytest.mark.skip\\ndef/' tests/test_calc.py",
        "perl -pi -e 's/^def/import pytest\\n\\@pytest.mark.xfail\\ndef/' tests/test_calc.py",
        "printf 'import calc\\ncalc.add = lambda a, b: a + b\\n' > conftest.py",
        "printf '[pytest]\\naddopts = --co\\n' > pytest.ini",
        "rm tests/test_calc.py && printf 'def test_ok():\\n    pass\\n' > tests/test_ok.py",
        "perl -pi -e 's/== 5/== -1/' tests/test_calc.py && git -c user.name=a -c user.email=a@a commit -qam ok",
    ],
)
def test_a_green_verify_from_a_gamed_test_is_not_verified(repo, workdir, monkeypatch, action):
    agent = workdir / "agent"
    agent.write_text(AGENT.format(action))
    agent.chmod(0o755)
    monkeypatch.setattr(runner, "OPENCODE", str(agent))
    row = runner.run("Fix calc.", VERIFY, str(repo), timeout=5)
    assert (row["exit_code"], row["tampered"], row["procedure_slug"]) == (1, True, None)


def test_the_agent_never_holds_the_openai_key(repo, workdir, monkeypatch):
    """#97: `graduate bench` needs the key in its env; an agent's `env` or `printenv` output lands in terminal.log,
    the dashboard and results/state.json."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-QWZXPLMK")
    agent = workdir / "agent"
    agent.write_text(AGENT.format('echo "key=${OPENAI_API_KEY-unset}"'))
    agent.chmod(0o755)
    monkeypatch.setattr(runner, "OPENCODE", str(agent))
    runner.run("Fix calc.", VERIFY, str(repo), timeout=5)
    assert "key=unset" in (workdir / "terminal.log").read_text()  # absent, not just empty
    assert not [p for p in workdir.rglob("*") if p.is_file() and "QWZX" in p.read_text(errors="ignore")]


def test_main_says_what_to_fix_before_launching_anything(repo, workdir, monkeypatch):
    """#83: wrong directory, no OpenCode, no router: one line each, not a traceback or a hang until --timeout."""
    task = workdir / "task.json"
    task.write_text('{"prompt": "Fix calc.", "verify": "true"}')
    monkeypatch.setattr(runner, "OPENCODE", "true")

    def main(task_file):
        monkeypatch.setattr(sys, "argv", ["graduate run", "--task-file", str(task_file), "--repo", str(repo)])
        with pytest.raises(SystemExit) as e:
            runner.main()
        return str(e.value.code)

    assert "run from the jelly checkout" in main(workdir / "demo-repo/tasks/01.json")
    assert "start `graduate up`" in main(task)
    monkeypatch.setattr(runner, "OPENCODE", str(workdir / "nope"))
    assert "opencode.ai/install" in main(task)
    assert not (workdir / "ledger.jsonl").exists()
