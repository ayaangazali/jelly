"""`graduate <command>`: the one dispatcher (N2, #57).

Adding a command is one line in COMMANDS: `"name": ("module:function", "one-line help")`.
The function takes no arguments and parses `sys.argv[1:]` as usual; the dispatcher strips the command name,
so a plain `argparse.ArgumentParser().parse_args()` sees only that command's flags.
Modules import lazily, so a command whose extras are missing breaks only itself.

`init` and `up` work in the current directory: init writes .env, prices.json, registry.json and opencode.json
there, and up serves the router from there. `up --demo` serves fixture state from a temp dir and needs no key.
"""

import argparse
import getpass
import importlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

COMMANDS = {
    "run": (
        "graduate.runner:main",
        "run one task through OpenCode and the router, verify, write a ledger row",
    ),
    "init": (
        "graduate.cli:init",
        "check Python and OpenCode, connect the OpenAI key, write .env and config",
    ),
    "up": (
        "graduate.cli:up",
        "start the router and watcher on :4141 and serve the dashboard (--demo: no key)",
    ),
    "bench": (
        "graduate.bench:main",
        "frontier vs small vs owned on the demo tasks: output tokens, cost, turns, pass rate",
    ),
    "results": (
        "graduate.results:main",
        "freeze the dashboard state to results/state.json; view it with ?state= (no key)",
    ),
    "train": (
        "graduate.registrar.train:main",
        "LoRA-train a task type's model, then TRAINING -> GRADUATED",
    ),
}

# The repo root in a checkout; site-packages in a wheel, where ui/ and fixtures/ ship beside graduate/.
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
OPENCODE = Path.home() / ".opencode/bin/opencode"
PROVIDER = {  # docs/demo-repo.md: the key OpenCode sends is the session id, never the OpenAI key
    "npm": "@ai-sdk/openai-compatible",
    "name": "GRADUATE router",
    "options": {
        "baseURL": "http://localhost:4141/v1",
        "apiKey": "{env:GRADUATE_SESSION}",
    },
    "models": {"graduate": {"name": "graduate"}},
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        width = max(map(len, COMMANDS))
        lines = [f"  {name:<{width}}  {help}" for name, (_, help) in COMMANDS.items()]
        print(
            "usage: graduate <command> [flags]\n\ncommands:\n" + "\n".join(lines),
            file=sys.stderr,
        )
        raise SystemExit(0 if argv and argv[0] in ("-h", "--help") else 2)
    module, func = COMMANDS[argv[0]][0].split(":")
    sys.argv = [f"graduate {argv[0]}", *argv[1:]]
    return getattr(importlib.import_module(module), func)()


def _dotenv():
    path = Path(".env")
    lines = path.read_text().splitlines() if path.exists() else []
    pairs = (line.partition("=") for line in lines if not line.lstrip().startswith("#"))
    return {k.strip(): v.strip().strip("'\"") for k, sep, v in pairs if sep}


def _write_dotenv(updates):
    """Set `updates` in .env, keep every other line. Mode 600 before the secret goes in."""
    path = Path(".env")
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [l for l in lines if l.partition("=")[0].strip() not in updates]
    path.touch(mode=0o600)
    path.chmod(0o600)
    path.write_text("\n".join(lines + [f"{k}={v}" for k, v in updates.items()]) + "\n")
    git = subprocess.run(["git", "check-ignore", "-q", ".env"], capture_output=True)
    if git.returncode == 1:  # a git repo that would commit .env; 128 = not a repo
        with open(".gitignore", "a") as f:
            f.write(".env\n")
        print("  added .env to .gitignore")


def init():
    import httpx

    p = argparse.ArgumentParser(
        prog="graduate init",
        description="Idempotent. CI: set OPENAI_API_KEY and pass --no-input.",
    )
    p.add_argument(
        "--no-input", action="store_true", help="never prompt; fail if no key"
    )
    p.add_argument(
        "--backend",
        choices=["river", "local", "none"],
        help="owned backend (default: river if RIVER_API_KEY, else local if transformers and torch import, else none)",
    )
    a = p.parse_args()
    env = {**_dotenv(), **os.environ}

    print(f"python {sys.version.split()[0]} ok")
    opencode = shutil.which("opencode") or (OPENCODE.exists() and str(OPENCODE))
    print(
        f"opencode {opencode}"
        if opencode
        else "opencode not found: the dashboard works, `graduate run` needs it (curl -fsSL https://opencode.ai/install | bash)"
    )

    from graduate.router.upstream import clean_key

    key = clean_key(env.get("OPENAI_API_KEY"))
    if not key and not a.no_input and sys.stdin.isatty():
        key = getpass.getpass("OPENAI_API_KEY (hidden): ").strip()
    if not key:
        sys.exit(
            "no OPENAI_API_KEY: export OPENAI_API_KEY=sk-... first, or run `graduate init` in a terminal to be asked; `graduate up --demo` needs no key"
        )
    base = env.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    try:  # the free endpoint: lists models, spends nothing
        r = httpx.get(
            base + "/models", headers={"Authorization": f"Bearer {key}"}, timeout=15
        )
    except httpx.HTTPError as e:
        sys.exit(f"cannot reach {base}/models: {e!r}")
    if r.status_code != 200:
        sys.exit(
            f"key rejected: GET {base}/models -> HTTP {r.status_code}; get a key at https://platform.openai.com/api-keys, or try `graduate up --demo` (no key)"
        )
    print(f"key ok: GET {base}/models -> 200")

    backend = a.backend or (
        "river"
        if env.get("RIVER_API_KEY")
        else "local"
        if all(map(importlib.util.find_spec, ("transformers", "torch")))
        else "none"
    )
    updates = {"OPENAI_API_KEY": key, "GRADUATE_OWNED_BACKEND": backend}
    if "OPENAI_BASE_URL" in env:
        updates["OPENAI_BASE_URL"] = base
    _write_dotenv(updates)
    print(f".env written (mode 600), owned backend: {backend}")

    if not Path("prices.json").exists():
        shutil.copy(FIXTURES / "prices.example.json", "prices.json")
        print("prices.json written")
    if not Path("registry.json").exists():
        from graduate import registry

        registry._write(registry.load())  # the empty registry, through its one writer
        print("registry.json written (empty)")

    oc = Path("opencode.json")
    cfg = (
        json.loads(oc.read_text())
        if oc.exists()
        else {"$schema": "https://opencode.ai/config.json"}
    )
    cfg.setdefault("provider", {})["graduate"] = PROVIDER
    cfg["model"] = "graduate/graduate"
    oc.write_text(json.dumps(cfg, indent=2) + "\n")
    print("opencode.json: provider `graduate` -> http://localhost:4141/v1")
    print("next: graduate up")


def _demo_dir():
    """A temp dir holding the fixture state /state reads (the same files fixtures/state.example.json was built from)."""
    work = Path(tempfile.mkdtemp(prefix="graduate-demo-"))
    state = json.loads((FIXTURES / "state.example.json").read_text())
    (work / "registry.json").write_text(json.dumps(state["registry"], indent=2))
    (work / "terminal.log").write_text("\n".join(state["terminal"]) + "\n")
    shutil.copy(FIXTURES / "ledger.example.jsonl", work / "ledger.jsonl")
    shutil.copy(FIXTURES / "trace.example.jsonl", work / "trace.jsonl")
    (work / "sessions").mkdir()
    shutil.copy(FIXTURES / "session.example.jsonl", work / "sessions/sess-demo.jsonl")
    return work


def _owned_backend():
    """Print the backend Approve trains a new run on, as train.backend() picks it, and warn about the River trap:
    with RIVER_API_KEY set and GRADUATE_OWNED_BACKEND unset it picks River, and an unfunded key fails there."""
    from graduate.registrar import train

    name = os.environ.get("GRADUATE_OWNED_BACKEND")
    try:
        river = isinstance(train.backend(), train.RiverBackend)
    except RuntimeError:  # GRADUATE_OWNED_BACKEND=none
        return print(
            "owned backend: none (GRADUATE_OWNED_BACKEND=none): Approve trains nothing, the frontier serves every call"
        )
    why = (
        f"GRADUATE_OWNED_BACKEND={name}"
        if name
        else "RIVER_API_KEY is set"
        if river
        else "no RIVER_API_KEY"
    )
    print(
        f"owned backend: {'river' if river else 'local'} ({why}): Approve trains {'on River' if river else 'on this machine'}"
    )
    if river and not name:
        print(
            "WARNING: RIVER_API_KEY is set and GRADUATE_OWNED_BACKEND is not, so Approve trains on River; an unfunded "
            "River account fails with insufficient_funds. GRADUATE_OWNED_BACKEND=local trains on this machine.",
            file=sys.stderr,
        )


def up():
    p = argparse.ArgumentParser(prog="graduate up")
    p.add_argument(
        "--demo",
        action="store_true",
        help="no key: serve the dashboard on fixture state",
    )
    a = p.parse_args()
    if (
        socket.socket().connect_ex(("127.0.0.1", 4141)) == 0
    ):  # #84: a bind check would trip on TIME_WAIT
        sys.exit(
            "port 4141 is taken: stop the other `graduate up` or `make dev` (find it: lsof -i :4141)"
        )
    if a.demo:
        os.chdir(_demo_dir())
        os.environ["GRADUATE_SAMPLE"] = (
            "1"  # the dashboard labels fixture numbers as sample data (#87)
        )
    elif not (os.environ.get("OPENAI_API_KEY") or _dotenv().get("OPENAI_API_KEY")):
        sys.exit(
            "no OPENAI_API_KEY here: run `graduate init` first, or `graduate up --demo`"
        )

    import uvicorn

    from graduate.router.app import app  # loads .env from the cwd
    from graduate.watcher import watch

    if (
        not a.demo
    ):  # the demo's registry is a fixture; a watcher would rebuild it from the ledger
        threading.Thread(target=watch, daemon=True).start()
    _owned_backend()
    print("dashboard: http://localhost:4141/   (Ctrl-C stops)", flush=True)
    uvicorn.run(
        app,
        host=os.environ.get("GRADUATE_HOST", "127.0.0.1"),
        port=4141,
        log_level="warning",
    )  # 0.0.0.0 in Docker (#58)
    print("stopped")


if __name__ == "__main__":
    main()
