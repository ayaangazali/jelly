"""`graduate <command>`: the one dispatcher (N2, #57).

Adding a command is one line in COMMANDS: `"name": ("module:function", "one-line help")`.
The function takes no arguments and parses `sys.argv[1:]` as usual; the dispatcher strips the command name,
so a plain `argparse.ArgumentParser().parse_args()` sees only that command's flags.
Modules import lazily, so a command whose extras are missing breaks only itself.
"""

import importlib
import sys

COMMANDS = {
    "run": (
        "graduate.runner:main",
        "run one task through OpenCode and the router, verify, write a ledger row",
    ),
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


if __name__ == "__main__":
    main()
