import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from graduate import trace

RECALL_LINE = re.compile(r"^\s*(?P<score>[0-9]*\.?[0-9]+)\s+(?P<slug>procedures/\S+)\s+\[(?P<matcher>\w+)\]", re.M)
MIN_SCORE = float(os.environ.get("GRADUATE_RECALL_MIN", "0.75"))
TIMEOUT = float(os.environ.get("GRADUATE_RECALL_TIMEOUT", "1.5"))
_cache = {}


def normalize(prompt):
    text = prompt.lower()
    text = re.sub(r"[\w./-]*[/.][\w./-]+", "<path>", text)
    text = re.sub(r"\d+", "<n>", text)
    return re.sub(r"\s+", " ", text).strip()


def name_from_prompt(prompt):
    words = re.sub(r"<[a-z]+>", " ", normalize(prompt))
    slug = re.sub(r"[^a-z0-9]+", "-", words).strip("-")
    if len(slug) > 40:
        slug = slug[:41].rsplit("-", 1)[0]
    return slug or "unknown"


def recall(prompt):
    binary = os.environ.get("MEMORABLE_BIN", "memorable")
    started = time.monotonic()
    try:
        out = subprocess.run([binary, "recall", prompt, "--single"], capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, round((time.monotonic() - started) * 1000), type(e).__name__
    ms = round((time.monotonic() - started) * 1000)
    m = RECALL_LINE.search(out.stdout)
    if not m:
        return None, ms, "no match"
    return (float(m["score"]), m["slug"], m["matcher"]), ms, None


def classify(session_id, prompt, hint=None, root=Path(".")):
    if session_id in _cache:
        return _cache[session_id]
    if hint:
        task_type, how = hint, "named by the runner"
    else:
        task_type, how = None, ""
        hit, ms, err = recall(prompt)
        slug_map_path = root / "data" / "slug_map.json"
        slug_map = json.loads(slug_map_path.read_text()) if slug_map_path.exists() else {}
        if hit and hit[0] >= MIN_SCORE and hit[1] in slug_map:
            task_type, how = slug_map[hit[1]], f"{hit[0]:.2f} {hit[1]} [{hit[2]}] · {ms} ms"
        else:
            reason = err or (f"{hit[0]:.2f} {hit[1]} below {MIN_SCORE} or unmapped" if hit else "no procedure")
            task_type, how = name_from_prompt(prompt), f"{reason} · {ms} ms → named from the prompt"
        trace.emit("Router → Memorable", f'memorable recall "{prompt[:40]}…" --single', f"{how} → {task_type}", 20,
                   nodes=["router", "memorable"], edges=["recall"], session_id=session_id)
    _cache[session_id] = (task_type, how)
    return task_type, how


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(classify(p, p))
