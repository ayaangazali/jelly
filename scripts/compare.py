"""Frontier vs owned from ledger rows only (#118): python scripts/compare.py LEDGER

Per task type and arm: n, mean turns, mean tool calls, mean cost and pass rate, each followed by the session ids
behind it. Frontier baseline = verified frontier sessions (contracts §2: exit 0, not an escalation rerun). Owned =
`routed_to: owned` rows with exit 0; a failed owned row counts against the pass rate and nowhere else.

Owned cost is shown on both bases: River list (the ledger's cost_usd, which the router prices with prices.json's
`owned` block, contracts §9) and local ($0 marginal, plus the training wall time from the newest `graduated` event in
the registry.json beside the ledger, when there is one).

Refuses stub data (exit 1): any row with the stub's model id, or an upstream-auth.log beside the ledger.
"""

import json
import re
import sys
from pathlib import Path

STUB_MODEL = "gpt-5.6-terra"  # only scripts/stub-upstream.py serves it (the prices.example.json frontier id)


def mean(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else None


def fmt(v, template):
    return "n/a" if v is None else template.format(v)


def ids(rows):
    return ", ".join(r["session_id"] for r in rows) or "none"


def training_secs(registry, task_type):
    """(seconds, event text) from the newest `graduated` event, which the trainer writes as '... in 612.3 s.'"""
    if not registry.exists():
        return None, "no registry.json beside the ledger"
    for e in json.loads(registry.read_text(encoding="utf-8"))["events"]:  # newest first
        m = re.search(r" in ([\d.]+) s\.$", e["text"])
        if e["kind"] == "graduated" and e["task_type"] == task_type and m:
            return float(m[1]), f'registry.json {e["ts"]}: "{e["text"]}"'
    return None, "no graduated event with a time in registry.json"


def main(path):
    ledger = Path(path)
    rows = [
        json.loads(l)
        for l in ledger.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    stub = [r["session_id"] for r in rows if r["model"] == STUB_MODEL]
    if stub or (ledger.parent / "upstream-auth.log").exists():
        why = (
            f"model {STUB_MODEL} on {', '.join(stub)}"
            if stub
            else "upstream-auth.log beside the ledger"
        )
        print(
            f"stub data, not a result ({why}: served by scripts/stub-upstream.py)",
            file=sys.stderr,
        )
        return 1
    print(f"ledger: {path} ({len(rows)} rows)")
    for task_type in sorted({r["task_type"] for r in rows}):
        of_type = [r for r in rows if r["task_type"] == task_type]
        arms = {
            "frontier": [
                r
                for r in of_type
                if r["routed_to"] == "frontier" and r["escalated_from"] is None
            ],
            "owned": [r for r in of_type if r["routed_to"] == "owned"],
        }
        passed = {
            arm: [r for r in tried if r["exit_code"] == 0]
            for arm, tried in arms.items()
        }
        print(f"\n{task_type}")
        for arm, tried in arms.items():
            ok = passed[arm]
            rate = f"{len(ok)}/{len(tried)}" + (
                f" ({100 * len(ok) / len(tried):.0f}%)" if tried else ""
            )
            print(
                f"  {arm}: n {len(ok)}, mean turns {fmt(mean(ok, 'turns'), '{:.2f}')}, "
                f"mean tool calls {fmt(mean(ok, 'tool_calls'), '{:.2f}')}, mean cost {fmt(mean(ok, 'cost_usd'), '${:.6f}')}"
                f"{' (River list)' if arm == 'owned' else ''}, pass rate {rate}"
            )
            print(f"    passed, in the means: {ids(ok)}")
            print(
                f"    failed, pass rate only: {ids([r for r in tried if r['exit_code'] != 0])}"
            )
        secs, source = training_secs(ledger.parent / "registry.json", task_type)
        print(
            f"  owned, local: mean cost $0 marginal; training wall time {fmt(secs, '{:.1f} s')} ({source})"
        )
        reruns = [
            r
            for r in of_type
            if r["routed_to"] == "frontier" and r["escalated_from"] is not None
        ]
        print(f"  escalation reruns, in neither arm: {ids(reruns)}")
        f, o = passed["frontier"], passed["owned"]
        if f and o:
            ft, ot, fc, oc = (
                mean(f, "turns"),
                mean(o, "turns"),
                mean(f, "cost_usd"),
                mean(o, "cost_usd"),
            )
            print(
                f"  fewer turns: {'yes' if ot < ft else 'no'} (owned {ot:.2f} vs frontier {ft:.2f}); "
                f"lower cost: River list {'yes' if oc < fc else 'no'} (${oc:.6f} vs ${fc:.6f}), local yes ($0 marginal)"
            )
        else:
            print("  fewer turns, lower cost: n/a (an arm has no passing rows)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__.splitlines()[0])
    sys.exit(main(sys.argv[1]))
