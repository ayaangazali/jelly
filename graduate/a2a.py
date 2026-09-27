"""Agent-to-agent procedures (#142): how verified agents fixed a task type, for the next agent on it.

Each verified run APPENDS one procedure (files touched, the fix in one line, the verify command, turns and
cost) to the task type's page; the page keeps the newest KEEP. The next agent's prompt gets only the newest
procedure plus a count. GBrain (`gbrain get/put a2a-<task_type>`, GBRAIN_BIN as in gbrain.py) when installed
and working, otherwise a shared file `a2a/<task_type>.md` in the working directory. Fails open: a2a never
fails a run.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from graduate import trace

ISSUE = 142
KEEP = 10
FILE_LABEL = "shared notes file (GBrain not installed)"
HEAD = "### "
SKILLS = Path(os.environ.get("GBRAIN_SKILLS", Path.home() / ".local/share/gbrain/skills"))
TOOLS = ("get_page", "search", "put_page")  # of GBrain's 144 MCP tools, the three this job needs
AGENT_RULES = """## Shared memory: GBrain (tools `gbrain_*`, skills brain-ops and query in your instructions)
1. First, before reading or editing code: call `gbrain_get_page` with slug `{page}` (procedures other agents verified on this task type).
2. Last, after the verify command passes: call `gbrain_put_page` with slug `{page}/{session}` and content: the files you changed, the fix in one line, the verify command.
"""


def _gbrain(*args, text=None, missing_ok=True):
    """stdout on exit 0, else None (missing CLI, missing page, a brain that won't open).

    With missing_ok=False, an installed CLI failing for any reason but a missing page raises instead, so a
    read that errored (a locked brain) is never mistaken for an empty page that `put` would then overwrite.
    """
    try:
        r = subprocess.run(
            [os.environ.get("GBRAIN_BIN", "gbrain"), *args],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        if missing_ok or isinstance(e, OSError):
            return None
        raise
    if r.returncode != 0 and not missing_ok and "page_not_found" not in r.stdout + r.stderr:
        raise RuntimeError(f"gbrain {args[0]} exit {r.returncode}: {(r.stderr or r.stdout).strip()[-200:]}")
    return r.stdout if r.returncode == 0 else None


def _names(task_type):
    return f"a2a-{task_type}", Path("a2a", f"{task_type}.md")


def _read(task_type, missing_ok=True):
    """(procedures oldest first, call, where), or None when there is no page."""
    slug, path = _names(task_type)
    page = _gbrain("get", slug, missing_ok=missing_ok)
    if page is not None:  # the page follows its YAML frontmatter
        body, call, where = page.split("\n---\n", 1)[-1], f"gbrain get {slug}", "GBrain"
    elif path.is_file():
        return _file(path), f"read {path}", FILE_LABEL
    else:
        return None
    return _procedures(body), call, where


def _file(path):
    return _procedures(path.read_text(encoding="utf-8"))


def _procedures(body):
    return [HEAD + p.strip() for p in ("\n" + body).split("\n" + HEAD)[1:]]


def render(task_type, procedures):
    return (
        f"# A2A procedures: {task_type}\n\n"
        f"How verified agents fixed {task_type}, newest last (keeps the newest {KEEP}).\n\n"
        + "\n\n".join(procedures)
        + "\n"
    )


def fix(removed, added):
    """The fix in one line: the first line taken out → the first line put in."""
    old = next((l.strip() for l in removed if l.strip()), "")
    new = next((l.strip() for l in added if l.strip()), "")
    return (
        f"`{old}` → `{new}`"
        if old and new
        else f"added `{new}`"
        if new
        else f"removed `{old}`"
        if old
        else "no line changed"
    )


def procedure(row, files, fix_line):
    return "\n".join(
        [
            f"{HEAD}{row['session_id']} · {row.get('ended_at') or 'unknown time'}",
            f"- files: {', '.join(files) or 'none'}",
            f"- fix: {fix_line}",
            f"- verify: `{row['verify_command']}` (exit {row['exit_code']})",
            f"- run: {row['turns']} turns · ${row['cost_usd']:.4f} · {row.get('model', 'unknown')}",
        ]
    )


def record(task_type, row, repo, before, after):
    """A verified run: diff the repo's trees before and after, then append its procedure."""
    try:

        def git(*a):
            return subprocess.run(
                ["git", *a, before, after], cwd=repo, capture_output=True, text=True
            ).stdout

        files = [
            f
            for f in git("diff-tree", "-r", "--name-only").split()
            if "__pycache__" not in f
        ]
        diff = [
            l
            for l in git("diff", "-U0").splitlines()
            if not l.startswith(("---", "+++"))
        ]
        line = fix(
            [l[1:] for l in diff if l.startswith("-")],
            [l[1:] for l in diff if l.startswith("+")],
        )
        put(task_type, procedure(row, files, line), row["session_id"])
    except Exception as e:
        print(f"a2a record skipped: {e!r}")


def rules(task_type, session_id):
    """What the agent's prompt says about using GBrain itself."""
    return AGENT_RULES.format(page=_names(task_type)[0], session=session_id)


def opencode_config(task_type, session_id, base=None):
    """OPENCODE_CONFIG_CONTENT that gives the agent GBrain's MCP server and memory skills, or None without the CLI."""
    gbrain = os.environ.get("GBRAIN_BIN", "gbrain")
    if not shutil.which(gbrain):
        return None
    path = Path(tempfile.gettempdir(), f"graduate-a2a-{session_id}.md")
    path.write_text(rules(task_type, session_id), encoding="utf-8")
    cfg = json.loads(base or "{}")
    cfg["mcp"] = {**cfg.get("mcp", {}), "gbrain": {"type": "local", "command": [gbrain, "serve"], "enabled": True}}
    cfg["tools"] = {**cfg.get("tools", {}), "gbrain_*": False, **{f"gbrain_{t}": True for t in TOOLS}}
    skills = [str(f) for f in (SKILLS / "brain-ops/SKILL.md", SKILLS / "query/SKILL.md") if f.is_file()]
    cfg["instructions"] = [*cfg.get("instructions", []), str(path), *skills]
    return json.dumps(cfg)


def get(task_type, session_id=None):
    """The short summary an agent's prompt gets: the newest procedure and how many the page holds."""
    try:
        got = _read(task_type)
        if not got or not got[0]:
            return None
        procedures, call, where = got
        note = f"Newest of {len(procedures)} verified procedures for {task_type}:\n{procedures[-1]}"
        trace.emit(
            "Runner → GBrain",
            call,
            f"read {len(procedures)} procedures · {where}",
            ISSUE,
            ["runner", "gbrain"],
            ["a2a-read"],
            session_id,
        )
        return note
    except Exception as e:
        print(f"a2a get skipped: {e!r}")
        return None


def put(task_type, entry, session_id):
    """Append one procedure to the page, keeping the newest KEEP.

    If GBrain errors on the read (not a missing page), the page is left alone and the shared file gets the
    procedure instead: a page this run could not read is never overwritten.
    """
    slug, path = _names(task_type)
    try:
        try:
            got, brain = _read(task_type, missing_ok=False), True
        except RuntimeError:
            got, brain = (_file(path), f"read {path}", FILE_LABEL) if path.is_file() else None, False
        procedures = [*((got or ([],))[0]), entry.strip()][-KEEP:]
        text = render(task_type, procedures)
        if brain and _gbrain("put", slug, "--force", text=text) is not None:
            call, where = f"gbrain put {slug} --force", "GBrain"
        else:
            path.parent.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8")
            call, where = f"write {path}", FILE_LABEL
        trace.emit("Runner → GBrain", call, f"appended, {len(procedures)} procedures · {where}", ISSUE, ["runner", "gbrain"], ["a2a-write"], session_id)
    except Exception as e:
        print(f"a2a put skipped: {e!r}")
