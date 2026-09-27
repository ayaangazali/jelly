"""A2A notes (#142): a verified run leaves a note for its task type, the next run on it gets the note, failures don't."""

import json
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


def test_a_verified_run_leaves_a_procedure_the_next_run_on_its_task_type_reads(repo, workdir, monkeypatch):
    monkeypatch.setenv("GBRAIN_BIN", str(workdir / "no-such-gbrain"))  # no CLI: file notes, no MCP
    agent(workdir, monkeypatch, FIX)
    first = runner.run("Fix calc.", VERIFY, str(repo), timeout=10, task_type="fix-calc")
    page = (workdir / "a2a/fix-calc.md").read_text()
    subprocess.run(["git", "checkout", "-q", "calc.py"], cwd=repo, check=True)  # broken again
    second = runner.run("Fix calc.", VERIFY, str(repo), timeout=10, task_type="fix-calc")

    assert (first["exit_code"], second["exit_code"]) == (0, 0)
    proc = (
        f"### {first['session_id']} · {first['ended_at']}\n- files: calc.py\n- fix: `return a - b` → `return a + b`\n"
        f"- verify: `{VERIFY}` (exit 0)\n- run: {first['turns']} turns · ${first['cost_usd']:.4f} · {first['model']}"
    )
    assert page == a2a.render("fix-calc", [proc])
    both = (workdir / "a2a/fix-calc.md").read_text()
    assert both.index(proc) < both.index(f"### {second['session_id']}")  # appended, not overwritten
    prompts = (workdir / "prompts").read_text().split("\n===\n")
    assert prompts[:2] == ["Fix calc.", f"## Notes from other agents\nNewest of 1 verified procedures for fix-calc:\n{proc}\n\nFix calc."]
    assert a2a_events() == [
        (["a2a-write"], first["session_id"], "write a2a/fix-calc.md"),
        (["a2a-read"], second["session_id"], "read a2a/fix-calc.md"),
        (["a2a-write"], second["session_id"], "write a2a/fix-calc.md"),
    ]
    assert first["prompt"] == second["prompt"] == "Fix calc."  # the ledger keeps the task's own prompt


def test_the_page_appends_and_keeps_the_newest_ten(workdir):
    for i in range(12):
        a2a.put("fix-calc", f"### sess-{i:02d} · t{i}\n- fix: `x` → `y`", f"sess-{i:02d}")
    page = (workdir / "a2a/fix-calc.md").read_text()
    assert [l for l in page.splitlines() if l.startswith("### ")] == [f"### sess-{i:02d} · t{i}" for i in range(2, 12)]
    assert a2a.get("fix-calc") == "Newest of 10 verified procedures for fix-calc:\n### sess-11 · t11\n- fix: `x` → `y`"


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
        'if [ "$1" = put ]; then cat > "$f"; elif [ -f "$f" ]; then printf -- "---\\ntype: note\\n---\\n\\n" && cat "$f"; '
        'else echo "Error [page_not_found]" >&2; exit 1; fi\n'
    )
    cli.chmod(0o755)
    monkeypatch.setenv("GBRAIN_BIN", str(cli))
    assert a2a.get("fix-calc", "sess-a") is None
    a2a.put("fix-calc", "### sess-a · t\n- files: calc.py", "sess-a")
    assert a2a.get("fix-calc", "sess-b") == "Newest of 1 verified procedures for fix-calc:\n### sess-a · t\n- files: calc.py"
    assert not (workdir / "a2a").exists()
    assert [(e["call"], e["result"]) for e in jsonl("trace.jsonl")] == [
        ("gbrain put a2a-fix-calc --force", "appended, 1 procedures · GBrain"),
        ("gbrain get a2a-fix-calc", "read 1 procedures · GBrain"),
    ]


def test_agents_get_gbrain_mcp_and_its_skills(workdir, monkeypatch):
    monkeypatch.setenv("GBRAIN_BIN", "false")  # any CLI on PATH
    monkeypatch.setattr(a2a, "SKILLS", workdir / "skills")
    (workdir / "skills/query").mkdir(parents=True)
    (workdir / "skills/query/SKILL.md").write_text("# Query Skill")
    cfg = json.loads(a2a.opencode_config("fix-calc", "sess-a", '{"provider": {"graduate": {}}}'))
    assert cfg["provider"] == {"graduate": {}}  # the router config stays
    assert cfg["mcp"] == {"gbrain": {"type": "local", "command": ["false", "serve"], "enabled": True}}
    assert cfg["tools"] == {"gbrain_*": False, "gbrain_get_page": True, "gbrain_search": True, "gbrain_put_page": True}
    rules, skill = cfg["instructions"]
    assert skill == str(workdir / "skills/query/SKILL.md")
    assert "`gbrain_get_page` with slug `a2a-fix-calc`" in open(rules).read() and "`a2a-fix-calc/sess-a`" in open(rules).read()
    monkeypatch.setenv("GBRAIN_BIN", str(workdir / "no-such-gbrain"))
    assert a2a.opencode_config("fix-calc", "sess-a") is None


def test_a_brain_that_errors_on_read_is_never_overwritten(workdir, monkeypatch):
    """A locked brain fails `get` with something other than page_not_found: the page is left alone, the file gets it."""
    cli = workdir / "gbrain"
    cli.write_text('#!/bin/sh\n[ "$1" = put ] && touch "$(dirname "$0")/wrote"\necho "Error [lock_timeout]: brain busy" >&2\nexit 1\n')
    cli.chmod(0o755)
    monkeypatch.setenv("GBRAIN_BIN", str(cli))
    a2a.put("fix-calc", "### sess-a · t", "sess-a")
    a2a.put("fix-calc", "### sess-b · t", "sess-b")
    assert not (workdir / "wrote").exists()
    assert (workdir / "a2a/fix-calc.md").read_text() == a2a.render("fix-calc", ["### sess-a · t", "### sess-b · t"])
    labels = [e["result"] for e in jsonl("trace.jsonl") if e["who"] == "Runner → GBrain"]
    assert labels == ["appended, 1 procedures · shared notes file (GBrain busy)", "appended, 2 procedures · shared notes file (GBrain busy)"]


def test_a_busy_brain_is_retried_before_the_file(workdir, monkeypatch):
    """Parallel agents' GBrain MCP servers hold the brain: a put that fails once, then works, lands in GBrain."""
    cli = workdir / "gbrain"
    cli.write_text(
        '#!/bin/sh\nd="$(dirname "$0")"\n'
        'if [ "$1" = get ]; then echo "Error [page_not_found]" >&2; exit 1; fi\n'
        'if [ ! -f "$d/busy-once" ]; then touch "$d/busy-once"; echo "The local persistence owner is unavailable." >&2; exit 1; fi\n'
        'cat > "$d/page"\n'
    )
    cli.chmod(0o755)
    monkeypatch.setenv("GBRAIN_BIN", str(cli))
    monkeypatch.setattr(a2a.time, "sleep", lambda s: None)
    a2a.put("fix-calc", "### sess-a · t", "sess-a")
    assert (workdir / "page").read_text() == a2a.render("fix-calc", ["### sess-a · t"])
    assert not (workdir / "a2a").exists()
