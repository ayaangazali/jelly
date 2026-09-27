"""A2A notes (#142): a verified run leaves a note for its task type, the next run on it gets the note, failures don't."""

import subprocess

from conftest import jsonl
from graduate import a2a, runner
from test_runner import AGENT, FIX, VERIFY, repo  # noqa: F401  (the scratch-repo fixture)


def agent(workdir, monkeypatch, action):
    """A fake OpenCode that records the prompt it got, then does `action` in the repo."""
    path = workdir / "agent"
    path.write_text(AGENT.format(f"printf '%s\\n===\\n' \"$2\" >> {workdir}/prompts\n{action}"))
    path.chmod(0o755)
    monkeypatch.setattr(runner, "OPENCODE", str(path))


def a2a_events():
    return [(e["edges"], e["session_id"], e["call"]) for e in jsonl("trace.jsonl") if e["who"] == "Runner → GBrain"]


def test_a_verified_run_leaves_a_note_the_next_run_on_its_task_type_reads(repo, workdir, monkeypatch):
    agent(workdir, monkeypatch, FIX)
    first = runner.run("Fix calc.", VERIFY, str(repo), timeout=10, task_type="fix-calc")
    note = (workdir / "a2a/fix-calc.md").read_text()
    subprocess.run(["git", "checkout", "-q", "calc.py"], cwd=repo, check=True)  # broken again
    second = runner.run("Fix calc.", VERIFY, str(repo), timeout=10, task_type="fix-calc")

    assert (first["exit_code"], second["exit_code"]) == (0, 0)
    assert note == f"{first['session_id']} passed: changed calc.py; `{VERIFY}` went green."
    prompts = (workdir / "prompts").read_text().split("\n===\n")
    assert prompts[:2] == ["Fix calc.", f"## Notes from other agents\n{note}\n\nFix calc."]
    assert a2a_events() == [
        (["a2a-write"], first["session_id"], "write a2a/fix-calc.md"),
        (["a2a-read"], second["session_id"], "read a2a/fix-calc.md"),
        (["a2a-write"], second["session_id"], "write a2a/fix-calc.md"),
    ]
    assert first["prompt"] == second["prompt"] == "Fix calc."  # the ledger keeps the task's own prompt


def test_a_failing_run_writes_nothing(repo, workdir, monkeypatch):
    agent(workdir, monkeypatch, "true")
    assert runner.run("Fix calc.", VERIFY, str(repo), timeout=10, task_type="fix-calc")["exit_code"] == 1
    assert not (workdir / "a2a").exists() and a2a_events() == []


def test_a_broken_backend_never_fails_a_run(repo, workdir, monkeypatch):
    (workdir / "a2a").write_text("not a directory")  # no gbrain (conftest), and the notes file can't be written
    agent(workdir, monkeypatch, FIX)
    row = runner.run("Fix calc.", VERIFY, str(repo), timeout=10, task_type="fix-calc")
    assert row["exit_code"] == 0 and jsonl("ledger.jsonl") == [row] and a2a_events() == []


def test_gbrain_backend_when_the_cli_works(workdir, monkeypatch):
    """`gbrain put <slug> --force` from stdin, `gbrain get <slug>` prints frontmatter then the page."""
    cli = workdir / "gbrain"
    cli.write_text(
        '#!/bin/sh\nf="$(dirname "$0")/page-$2"\n'
        'if [ "$1" = put ]; then cat > "$f"; else [ -f "$f" ] && printf -- "---\\ntype: note\\n---\\n\\n" && cat "$f"; fi\n'
    )
    cli.chmod(0o755)
    monkeypatch.setenv("GBRAIN_BIN", str(cli))
    assert a2a.get("fix-calc", "sess-a") is None
    a2a.put("fix-calc", "changed calc.py", "sess-a")
    assert a2a.get("fix-calc", "sess-b") == "changed calc.py"
    assert not (workdir / "a2a").exists()
    assert [(e["call"], e["result"]) for e in jsonl("trace.jsonl")] == [
        ("gbrain put a2a-fix-calc --force", "wrote 15 chars · GBrain"),
        ("gbrain get a2a-fix-calc", "read 15 chars · GBrain"),
    ]
