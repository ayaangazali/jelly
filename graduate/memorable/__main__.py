import argparse
import json
import sys

from graduate.memorable.bridge import build_trace, ingest

parser = argparse.ArgumentParser(prog="python -m graduate.memorable")
sub = parser.add_subparsers(dest="cmd", required=True)
for name in ("ingest", "trace"):
    p = sub.add_parser(name)
    p.add_argument("session_id")
    p.add_argument("--verify", dest="verify_command")
    p.add_argument("--exit-code", type=int)
args = parser.parse_args()

if args.cmd == "trace":
    print(json.dumps(build_trace(args.session_id, args.verify_command, args.exit_code), indent=2))
else:
    slug = ingest(args.session_id, verify_command=args.verify_command, exit_code=args.exit_code)
    print(slug or "no procedure")
    sys.exit(0 if slug else 1)
