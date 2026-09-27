#!/usr/bin/env bash
# jelly-preview-pull.service (#55): fast-forward the preview clone; when HEAD moved, restart the preview
# (reinstalling first when pyproject.toml changed).
set -euo pipefail
cd "$(dirname "$0")/../.."
before=$(git rev-parse HEAD)
git pull -q --ff-only
[ "$(git rev-parse HEAD)" = "$before" ] && exit 0
git diff --quiet "$before" HEAD -- pyproject.toml || "$HOME/.local/bin/uv" pip install -q --python .venv/bin/python -e .
systemctl --user restart jelly-preview.service
echo "preview: $before -> $(git rev-parse --short HEAD)"
