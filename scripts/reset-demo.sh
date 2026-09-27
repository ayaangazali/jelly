#!/usr/bin/env bash
# Usage: scripts/reset-demo.sh 01..10|clean
# Restores demo-repo/ to HEAD (drops edits and untracked files; keeps .venv),
# then plants broken state NN: one changed line that fails tests/test_mod_NN.py.
set -euo pipefail

case "${1:-}" in
clean) ;;
01) old='a + b' new='a - b' ;;
02) old='n % 2 == 0' new='n % 2 == 1' ;;
03) old='width * height' new='width + height' ;;
04) old='9 / 5 + 32' new='9 / 5 + 23' ;;
05) old='sum(values) / len' new='sum(values) // len' ;;
06) old='max(values)' new='min(values)' ;;
07) old='"aeiou"' new='"aeio"' ;;
08) old='range(2, n + 1)' new='range(2, n)' ;;
09) old='reversed(text.split())' new='text.split()' ;;
10) old='100 * part' new='10 * part' ;;
*)
  echo "usage: $0 01..10|clean" >&2
  exit 2
  ;;
esac

cd "$(dirname "$0")/.."
git restore --source=HEAD --worktree -- demo-repo
git clean -fdq -- demo-repo
# Same-size edits within one second leave stale .pyc files that Python trusts.
find demo-repo -path demo-repo/.venv -prune -o -name __pycache__ -exec rm -rf {} +
[ "$1" = clean ] && exit 0

python3 - "demo-repo/calc/mod_$1.py" "$old" "$new" <<'PY'
import sys
path, old, new = sys.argv[1:]
src = open(path).read()
assert src.count(old) == 1, f"{path}: expected exactly one {old!r}"
open(path, "w").write(src.replace(old, new))
PY
