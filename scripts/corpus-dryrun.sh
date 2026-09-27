#!/usr/bin/env bash
# Offline dry run of #13 and #6 end to end, zero OpenAI calls: stub upstream (scripts/stub-upstream.py) -> router ->
# OpenCode -> runner -> ledger, session logs, stage split, registry, backup, durable copy, restore.
# Run from an activated .venv with ports 4141 and 4199 free and no corpus data in the repo root.
# Everything it writes ends in backups/dryrun-<time>/.
set -euo pipefail
cd "$(dirname "$0")/.."
for f in ledger.jsonl metrics.jsonl sessions registry.json; do
  [ ! -e $f ] || {
    echo "$f exists: move it aside first" >&2
    exit 1
  }
done
out=backups/dryrun-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$out"
own_prices=
[ -e prices.json ] || {
  cp fixtures/prices.example.json prices.json
  own_prices=1
}
python3 scripts/stub-upstream.py 4199 "$out/upstream-auth.log" &
stub=$!
OPENAI_BASE_URL=http://127.0.0.1:4199/v1 OPENAI_API_KEY=sk-stub uvicorn graduate.router.app:app --port 4141 2>"$out/router.log" &
router=$!
trap 'kill $stub $router; [ -z "$own_prices" ] || rm prices.json' EXIT
until curl -sf localhost:4141/healthz >/dev/null; do sleep 0.2; done
check() { "$@" >/dev/null || {
  echo "FAIL: $*" >&2
  exit 1
}; }
stash() { mkdir -p "$1" && mv ledger.jsonl metrics.jsonl sessions registry.json backups/stage-ledger.jsonl backups/corpus-*.tgz "$1"/; }

# Caps: a stub session is 4 calls, so a 6-call cap stops inside the second of three states.
CAP_CALLS=6 STATES="01 02 03" CORPUS_DIR=$out/capped-copy scripts/corpus.sh | tee "$out/capped.txt"
check grep -q "CAP HIT" "$out/capped.txt"
check jq -se 'length == 2' ledger.jsonl backups/stage-ledger.jsonl
stash "$out/capped"

CORPUS_DIR=$out/copy scripts/corpus.sh | tee "$out/full.txt"
check jq -se 'length == 4 and all(.exit_code == 0 and .task_type == "fix-failing-test")' ledger.jsonl
check jq -se 'length == 4 and all(.exit_code == 0)' backups/stage-ledger.jsonl
check jq -e '.task_types["fix-failing-test"] | .verified_runs == 4 and .state == "LEARNING"' registry.json
for s in $( # a log per session, with the edit round trip
  jq -r .session_id ledger.jsonl backups/stage-ledger.jsonl
); do
  check jq -se 'any(.[].response.tool_calls[]?; .function.name == "edit")' "sessions/$s.jsonl"
done
check grep -Eq "cached share [1-9]" "$out/full.txt"
check jq -Rse 'split("\n") | map(select(. != "")) | length > 0 and all(. == "Bearer sk-stub")' "$out/upstream-auth.log"

# Restore from the durable copy's tarball into a clean dir: same files, and the watcher rebuilds 4 of 5.
mkdir "$out/restore"
tar xzf "$out"/copy/corpus-*.tgz -C "$out/restore"
for f in ledger.jsonl sessions registry.json metrics.jsonl backups/stage-ledger.jsonl; do check diff -r "$f" "$out/restore/$f"; done
rm "$out/restore/registry.json"
(cd "$out/restore" && PYTHONPATH=$OLDPWD python -m graduate.watcher --once >/dev/null)
check jq -e '.task_types["fix-failing-test"].verified_runs == 4' "$out/restore/registry.json"
stash "$out/full"
echo "dry run ok: $out"
