.PHONY: dev ui check

dev:
	uvicorn graduate.router.app:app --reload --port 4141

ui:
	python -m webbrowser http://localhost:4141/

# Imports every module, then runs the self-checks that exist (#14, #18).
check:
	python -c "import pkgutil, importlib, graduate; [importlib.import_module(m.name) for m in pkgutil.walk_packages(graduate.__path__, 'graduate.')]"
	python -m graduate.reward
	python -m graduate.registry
