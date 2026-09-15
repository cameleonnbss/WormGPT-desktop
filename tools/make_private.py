"""Fill the telemetry credentials into a PRIVATE build of the source tree.

Usage (owner only, never commit the result):
    python tools/make_private.py --token <BOT_TOKEN> --guild <GUILD_ID>

It rewrites wormgpt/telemetry.py in place with the real constants so the
next `pyinstaller` build ships with logging enabled. Public/shared trees
keep the empty defaults (module self-disabled).
"""
import argparse
import re
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "wormgpt" / "telemetry.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--guild", required=True, type=int)
    args = ap.parse_args()

    src = TARGET.read_text(encoding="utf-8")
    src, n1 = re.subn(r'^BOT_TOKEN = ""', f'BOT_TOKEN = "{args.token}"',
                      src, count=1, flags=re.M)
    src, n2 = re.subn(r'^GUILD_ID = 0', f"GUILD_ID = {args.guild}",
                      src, count=1, flags=re.M)
    if n1 != 1 or n2 != 1:
        print("pattern not found — telemetry.py layout changed?", file=sys.stderr)
        return 1
    TARGET.write_text(src, encoding="utf-8")
    print("telemetry.py: credentials injected (private build).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
