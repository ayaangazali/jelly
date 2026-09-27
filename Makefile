.PHONY: dev ui check

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
