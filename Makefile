.PHONY: dev ui check test screens record e2e-replay e2e

dev:
	uvicorn graduate.router.app:app --reload --port 4141

ui:
	python -m webbrowser http://localhost:4141/

# Imports every module except `__main__` entry points, then runs the self-checks that exist (#14, #18, #21, #23).
check:
	python -c "import pkgutil, importlib, graduate; [importlib.import_module(m.name) for m in pkgutil.walk_packages(graduate.__path__, 'graduate.') if not m.name.endswith('.__main__')]"
	python -m graduate.reward
	python -m graduate.registry
	python -m graduate.registrar.dataset --check
	python -m graduate.escalator

# Offline: the frontier is a stub (tests/conftest.py). pip install -e .[test] first.
test:
	pytest -q

# Dashboard screenshots at 1920x1080 and 1280x720 into docs/screens/; fails on console errors or overflow (#55).
screens:
	python scripts/screens.py

# $0 and deterministic (#65): real OpenCode + the demo repo's pytest against scripts/stub-upstream.py, which replays
# one scripted session (read, edit, "Fixed.") per broken state. Drives scripts/corpus-dryrun.sh.
e2e-replay:
	scripts/corpus-dryrun.sh

# Backup video of scripts/demo.sh on the presenter dashboard (#31). Offline by default; ARGS= passes demo.sh flags.
record:
	python scripts/record.py $(ARGS)

# One live OpenCode session on the cheapest model, caps $0.10 and 20 calls (#59). Skips (exit 0) with no key or no credit.
e2e:
	python -m graduate.e2e
