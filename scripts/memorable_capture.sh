#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

M=(npx -y memorable-cli@0.5.30)
OUT=fixtures/memorable

run() {
  local name=$1
  shift
  echo "\$ memorable $*"
  (cd /tmp && "${M[@]}" "$@" 2>&1) | tee "$OUT/$name" || true
}

status=$( (cd /tmp && "${M[@]}" status 2>&1) )
if grep -q "not configured, run \`memorable login\`" <<<"$status"; then
  echo "Not logged in. Run: npx memorable-cli@0.5.30 login" >&2
  exit 1
fi
if grep -qE "consent not chosen|write consent +(unset|off)" <<<"$status"; then
  echo "Write consent is off. Run: npx memorable-cli@0.5.30 enable" >&2
  exit 1
fi

run status.txt status
for trace in "$OUT"/trace-*.json; do
  run "ingest-$(basename "$trace" .json).txt" ingest "$PWD/$trace"
done
run list.json list --json

start=$(python3 -c 'import time; print(time.time())')
run recall-fix-failing-test.txt recall "The test tests/test_mod_03.py is failing. Fix the code so it passes." --single
end=$(python3 -c 'import time; print(time.time())')
python3 -c "print(f'recall_ms={round(($end - $start) * 1000)}')" | tee "$OUT/recall-timing.txt"

run recall-changelog.txt recall "Add a CHANGELOG entry for version 0.4.3." --single
run chain.json chain "fix the failing test" --json

slug=$(grep -oE 'procedures/[A-Za-z0-9_-]+' "$OUT/recall-fix-failing-test.txt" | head -1 || true)
if [[ -n "$slug" ]]; then
  run show.txt show "$slug"
fi

HOME_DIR="$HOME" perl -pi -e 's/\Q$ENV{HOME_DIR}\E/~/g; s/mk_[A-Za-z0-9_-]*/mk_REDACTED/g' "$OUT"/*.txt "$OUT"/*.json
echo "Saved to $OUT/"
