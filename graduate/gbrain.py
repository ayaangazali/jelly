"""Stretch: GRADUATED.md into GBrain (#28)."""

import os
import subprocess

from graduate import trace


def render(task_types):
    lines = ["# Graduated task types", ""]
    for name, tt in sorted(task_types.items()):
        if tt["state"] != "GRADUATED":
            continue
        b, c = tt.get("baseline") or {}, tt.get("current") or {}
        lines.append(
            f"- {name}: graduated {tt['graduated_at']}, {tt['verified_runs']} runs,"
            f" turns {b.get('turns')} → {c.get('turns')},"
            f" cost ${b.get('cost_usd')} → ${c.get('cost_usd')}"
        )
    return "\n".join(lines) + "\n"


def publish(task_types, path):
    try:
        md = render(task_types)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        r = subprocess.run(
            [os.environ.get("GBRAIN_BIN", "gbrain"), "put", "graduated", "--force"],
            input=md,
            text=True,
            capture_output=True,
            timeout=30,
        )
        result = f"exit {r.returncode}"
    except Exception as e:
        result = f"skipped: {e!r}"
    trace.emit(
        "Registry → GBrain", "gbrain put graduated --force", result, 28, ["registry", "disk"]
    )
