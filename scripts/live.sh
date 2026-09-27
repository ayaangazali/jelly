#!/usr/bin/env bash
# The live path in one command, for when OpenAI credit shows up (#31): a 1-token credit probe that refuses without
# credit, then the real corpus (scripts/corpus.sh), a retrain on it (graduate train --corpus), then the live demo on
# that checkpoint, filmed (scripts/record.py runs scripts/demo.sh; numbers -> docs/results.md, video -> docs/recordings/).
#
#   (set -a; . ~/super.env; set +a; scripts/live.sh)   # ~25 min: corpus ~5 (caps USD 6, 400 calls), CPU training ~10, demo ~5
#   scripts/live.sh --offline                           # the same chain on scripts/stub-upstream.py: zero OpenAI calls
#
# CORPUS_DIR (live default /home/ubuntu/jelly-corpus-live, never the stub corpus) gets the corpus and the checkpoint.
# Needs what demo.sh needs: an activated .venv with '.[test,train]', OpenCode, free ports.
set -euo pipefail
cd "$(dirname "$0")/.."
offline=
[ "${1:-}" != --offline ] || offline=1
T=fix-failing-test PORT=${PORT:-4171}
CORPUS_DIR=$(realpath -m "${CORPUS_DIR:-$([ -n "$offline" ] && echo backups/live-offline-corpus || echo /home/ubuntu/jelly-corpus-live)}")
export GRADUATE_ROUTER=http://localhost:$PORT OPENCODE_CONFIG_CONTENT='{"provider":{"graduate":{"options":{"baseURL":"http://localhost:'$PORT'/v1"}}}}'
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT
if [ -n "$offline" ]; then
 python3 scripts/stub-upstream.py $((PORT + 1)) /dev/null &
 pids+=("$!")
 export OPENAI_BASE_URL=http://127.0.0.1:$((PORT + 1))/v1 OPENAI_API_KEY=sk-stub
 sleep 1
fi
[ -n "${OPENAI_API_KEY:-}" ] || {
 echo "no OPENAI_API_KEY: (set -a; . ~/super.env; set +a; scripts/live.sh)" >&2
 exit 1
}
why=$(python -c 'import os; from graduate import e2e; print(e2e.probe(os.environ["OPENAI_API_KEY"]) or "")')
[ -z "$why" ] || {
 echo "refused: $why. Nothing ran; docs/results.md and the offline rehearsal stay as they are." >&2
 exit 1
}

python -c 'import playwright, river_client, torch' 2>/dev/null || {
 echo "needs pip install -e '.[test,train]' playwright (step 3 films the demo)" >&2
 exit 1
}
echo "== 1/3 corpus -> $CORPUS_DIR"
out=backups/live-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$out"
for f in ledger.jsonl metrics.jsonl sessions registry.json registry.lock trace.jsonl data prices.json; do
 [ ! -e $f ] || mv $f "$out/"
done
# the frontier model and its prices for the corpus (docs/corpus.md); corpus.sh keeps a copy for demo.sh
jq '.frontier = {model: "gpt-4.1-mini", input: 0.4, cached_input: 0.1, output: 1.6}' fixtures/prices.example.json >prices.json
uvicorn graduate.router.app:app --port "$PORT" >"$out/router.log" 2>&1 &
router=$!
pids+=("$router")
until curl -sf localhost:$PORT/healthz >/dev/null; do sleep 0.2; done
CORPUS_DIR=$CORPUS_DIR scripts/corpus.sh

echo "== 2/3 retrain $T on all of $CORPUS_DIR (the operator running this is the consent)"
cat "$CORPUS_DIR/stage-ledger.jsonl" >>ledger.jsonl # corpus.sh held these back for the demo's fifth run
python -m graduate.watcher --once                   # READY: 5 or more verified
python -c "from graduate import registry; registry.set_consent('$T', True)"
graduate train $T --corpus "$CORPUS_DIR"
ckpt=$(jq -r --arg t $T '.task_types[$t].model' registry.json)
mkdir -p "$CORPUS_DIR/checkpoints" && cp -r "$ckpt" "$CORPUS_DIR/checkpoints/" # demo.sh moves data/ aside
ckpt=$CORPUS_DIR/checkpoints/$(basename "$ckpt")

echo "== 3/3 the demo on $ckpt, filmed"
kill "$router" # demo.sh starts its own
CORPUS_DIR=$CORPUS_DIR python scripts/record.py ${offline:+--offline} --auto-approve --use-checkpoint "$ckpt"
