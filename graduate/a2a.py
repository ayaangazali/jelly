"""Agent-to-agent notes (#142): what the last verified agent did on a task type, for the next agent on it.

GBrain (`gbrain get/put a2a-<task_type>`, GBRAIN_BIN as in gbrain.py) when installed and working, otherwise a
shared file `a2a/<task_type>.md` in the working directory. Fails open: a2a never fails a run.
"""

import os
import subprocess
from pathlib import Path

from graduate import trace

ISSUE = 142
FILE_LABEL = "shared notes file (GBrain not installed)"


def _gbrain(*args, text=None):
    """stdout on exit 0, else None (missing CLI, missing page, a brain that won't open)."""
    try:
        r = subprocess.run(
            [os.environ.get("GBRAIN_BIN", "gbrain"), *args],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _names(task_type):
    return f"a2a-{task_type}", Path("a2a", f"{task_type}.md")


def get(task_type, session_id=None):
    slug, path = _names(task_type)
    try:
        page = _gbrain("get", slug)
        if page is not None:  # the page follows its YAML frontmatter
            note, call, where = (
                page.split("\n---\n", 1)[-1],
                f"gbrain get {slug}",
                "GBrain",
            )
        elif path.is_file():
            note, call, where = (
                path.read_text(encoding="utf-8"),
                f"read {path}",
                FILE_LABEL,
            )
        else:
            return None
        note = note.strip()
        trace.emit("Runner → GBrain", call, f"read {len(note)} chars · {where}", ISSUE, ["runner", "gbrain"], ["a2a-read"], session_id)
        return note
    except Exception as e:
        print(f"a2a get skipped: {e!r}")
        return None


def put(task_type, text, session_id):
    slug, path = _names(task_type)
    try:
        if _gbrain("put", slug, "--force", text=text) is not None:
            call, where = f"gbrain put {slug} --force", "GBrain"
        else:
            path.parent.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8")
            call, where = f"write {path}", FILE_LABEL
        trace.emit("Runner → GBrain", call, f"wrote {len(text)} chars · {where}", ISSUE, ["runner", "gbrain"], ["a2a-write"], session_id)
    except Exception as e:
        print(f"a2a put skipped: {e!r}")
