#!/usr/bin/env bash
# QA timer (#63): every check on the latest main, from a dedicated clone. Install: docs/QA.md, "QA timer".
# Log: qa-runs/<stamp>.log. Summary: qa-runs/latest.txt, one line: time, sha, pass/fail per check.
# A check that fails now but did not fail last run opens ONE issue with its log tail (keys scrubbed); while it stays
# failing, no more. QA_KEY_FILE (a file with OPENAI_API_KEY=...) is read for `make e2e` only: it skips without credit.
set -uo pipefail
cd "$(dirname "$0")/../.."
if [ -z "${QA_PULL:-}" ]; then # a fresh main, then that main's copy of this script
  git fetch -q origin && git reset -q --hard origin/main && QA_PULL=pass || QA_PULL=fail
  QA_PULL=$QA_PULL exec "$PWD/scripts/qa-timer/qa-run.sh"
fi
. .venv/bin/activate
# Run state a crashed or finished run left in the root (demo.sh keeps its own copy in backups/demo-*/before/).
rm -rf ledger.jsonl metrics.jsonl sessions registry.json registry.lock trace.jsonl terminal.log data bench prices.json
find backups -mindepth 1 -maxdepth 1 -mtime +1 -exec rm -rf {} + 2>/dev/null
scripts/reset-demo.sh clean
mkdir -p qa-runs
stamp=$(date -u +%Y%m%dT%H%M%SZ)
log=qa-runs/$stamp.log sha=$(git rev-parse --short HEAD) prev=$(cat qa-runs/latest.txt 2>/dev/null)
line="$(date -u +%FT%TZ) $sha pull=$QA_PULL"

check() { # check NAME CMD...
  echo "#### qa: $1" >>"$log"
  "${@:2}" >>"$log" 2>&1 && line+=" $1=pass" || line+=" $1=fail"
}
e2e() { OPENAI_API_KEY=$([ -r "${QA_KEY_FILE:-}" ] && . "$QA_KEY_FILE" && printf %s "${OPENAI_API_KEY:-}") make e2e; }
check test make test
check e2e-replay make e2e-replay
check demo env PORT=4541 scripts/demo.sh --offline --auto-approve --use-checkpoint river://offline-rehearsal/fix-failing-test-v1
check e2e e2e
echo "$line" | tee -a "$log" >qa-runs/latest.txt

for r in ${line#* * }; do
  name=${r%=*}
  [ "${r#*=}" = fail ] && [[ " $prev " != *" $r "* ]] || continue
  tail=$(awk -v m="#### qa: $name" '$0 == m { on = 1; next } /^#### qa: / { on = 0 } on' "$log" | tail -n 60 |
    sed -E 's/sk-[A-Za-z0-9_-]{8,}/sk-***/g')
  gh api "repos/{owner}/{repo}/issues" -f title="QA timer: $name failing on main at $sha" --jq .html_url \
    -f body="$(printf 'The QA timer on `%s` (scripts/qa-timer/) ran `%s` on main at %s and it failed; it passed or did not run last time.\n\nSummary: `%s`\nFull log on that host: `%s`\n\nLast 60 lines:\n```\n%s\n```' \
      "$(hostname)" "$name" "$sha" "$line" "$PWD/$log" "$tail")" >>"$log" 2>&1
done
