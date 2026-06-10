import argparse
import sys
from pathlib import Path

from freeact import config
from freeact.permissions import PermissionManager


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="freeact", description="Freeact code action agent")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("init", help="Initialize workspace configuration without starting")
    subparsers.add_parser("run", help="Start an interactive conversation (default)")
    return parser


def main() -> None:
    """CLI entry point.

    The interactive terminal UI is rebuilt in a later rewrite phase; until
    then only `freeact init` is functional.
    """
    parser = create_parser()
    args = parser.parse_args()

    match args.command:
        case "init":
            working_dir = Path.cwd()
            config.init(working_dir)
            PermissionManager(working_dir=working_dir, freeact_dir=working_dir / config.FREEACT_DIR_NAME).init()
            print(f"Initialized freeact workspace in {working_dir / config.FREEACT_DIR_NAME}")
        case _:
            print(
                "The freeact terminal UI is being rebuilt and is not available "
                "in this development snapshot. Use the Python SDK (freeact.Agent) "
                "or `freeact init`.",
                file=sys.stderr,
            )
            raise SystemExit(1)


if __name__ == "__main__":
    main()
