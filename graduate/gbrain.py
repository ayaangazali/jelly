"""Stretch: GRADUATED.md into GBrain (#28)."""

import os
import subprocess

from graduate import trace


def _num(v, fmt):
    return "not measured yet" if v is None else fmt.format(v)


def render(task_types):
    lines = ["# Graduated task types", ""]
    grads = sorted(
        (n, tt) for n, tt in task_types.items() if tt["state"] == "GRADUATED"
    )
    if not grads:
        others = ", ".join(
            f"{n} is {tt['state']} with {tt.get('verified_runs', 0)} verified runs"
            for n, tt in sorted(task_types.items())
        )
        lines.append(f"Nothing has graduated yet{f' ({others})' if others else ''}.")
    for name, tt in grads:
        b, c = tt.get("baseline") or {}, tt.get("current") or {}
        lines += [
            f"## {name}",
            f"- checkpoint: {tt.get('model') or 'none recorded'}",
            f"- verified runs: {tt['verified_runs']}",
            f"- graduated: {tt['graduated_at']}",
            f"- turns, frontier baseline → owned model now: {_num(b.get('turns'), '{:.1f}')} → {_num(c.get('turns'), '{:.1f}')}",
            f"- cost per run, frontier baseline → owned model now: {_num(b.get('cost_usd'), '${:.4f}')} → {_num(c.get('cost_usd'), '${:.4f}')}",
            "",
        ]
    return "\n".join(lines).rstrip("\n") + "\n"


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
        "Registry → GBrain",
        "gbrain put graduated --force",
        result,
        28,
        ["registry", "disk"],
    )
