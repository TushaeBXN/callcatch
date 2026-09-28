"""
Validate client configs. Exit code 1 if any config is invalid.

    python tests/validate_config.py                     # every clients/*/config.yaml
    python tests/validate_config.py clients/acme-hvac/config.yaml
    python tests/validate_config.py --require-private   # deploy mode: PRIVATE values must exist

Runs in: the pre-commit hook, CI on every pull request, and (through
backend/prompt_builder.py) the test runner and future deploys.
The rules live in backend/config_schema.py.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from backend.config_schema import load_client_config
except ImportError as e:
    sys.exit(f"Can't load the validator ({e}). Inside your virtual environment run: pip install pyyaml")


def main():
    parser = argparse.ArgumentParser(description="Validate CallCatch client configs.")
    parser.add_argument("paths", nargs="*", help="config.yaml files (default: all clients/*/config.yaml)")
    parser.add_argument("--require-private", action="store_true",
                        help="Deploy mode: every PRIVATE value must be present in private/contacts.yaml")
    args = parser.parse_args()

    paths = [Path(p) for p in args.paths] or sorted((ROOT / "clients").glob("*/config.yaml"))
    if not paths:
        sys.exit("No client configs found.")

    failed = 0
    for path in paths:
        _, res = load_client_config(path, require_private=args.require_private)
        try:
            label = path.resolve().relative_to(ROOT)
        except ValueError:
            label = path
        status = "OK" if res.ok else "INVALID"
        print(f"{status:8} {label}")
        for e in res.errors:
            print(f"  ERROR    {e}")
        for w in res.warnings:
            print(f"  warning  {w}")
        if not res.ok:
            failed += 1

    if failed:
        print(f"\n{failed} config(s) invalid. Fix the ERROR lines above. Warnings don't block.")
        sys.exit(1)
    print("\nAll configs valid.")


if __name__ == "__main__":
    main()
