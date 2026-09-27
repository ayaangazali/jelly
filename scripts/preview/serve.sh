#!/usr/bin/env bash
# jelly-preview.service (#55): the real router on fixture state (what `graduate up --demo` serves, labelled sample data)
# at $PREVIEW_HOST:$PREVIEW_PORT, from the checkout this script lives in.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec .venv/bin/python -c 'import os, uvicorn
from graduate import cli
os.chdir(cli._demo_dir())
os.environ["GRADUATE_SAMPLE"] = "1"
from graduate.router.app import app
uvicorn.run(app, host=os.environ.get("PREVIEW_HOST", "127.0.0.1"), port=int(os.environ.get("PREVIEW_PORT", "4150")), log_level="warning")'
