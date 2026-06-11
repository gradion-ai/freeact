import argparse
import asyncio
import logging
import uuid
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from freeact import config
from freeact.agent import Agent
from freeact.permissions import PermissionManager
from freeact.terminal import TerminalApp
from freeact.tools.pytools.apigen import generate_mcp_sources

logger = logging.getLogger("freeact")


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the freeact CLI."""
    parser = argparse.ArgumentParser(
        prog="freeact",
        description="Freeact code action agent",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "init"],
        help="Command to execute (default: run)",
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Run code execution in sandbox mode",
    )
    parser.add_argument(
        "--sandbox-config",
        type=Path,
        metavar="PATH",
        help="Path to sandbox configuration file",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Set the logging level (default: info)",
    )
    parser.add_argument(
        "--session-id",
        type=uuid.UUID,
        metavar="UUID",
        help="Session UUID to resume (default: generate a new UUID)",
    )
    parser.add_argument(
        "--skip-permissions",
        action="store_true",
        help="Run tools without prompting for approval",
    )
    return parser


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = create_parser()
    return parser.parse_args()


def configure_logging(level: str) -> None:
    """Configure logging for the freeact package.

    Args:
        level: Log level name (debug, info, warning, error, critical).
    """
    logger = logging.getLogger("freeact")
    logger.setLevel(getattr(logging, level.upper()))
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)


def initialize(working_dir: Path) -> config.FreeactConfig:
    """Initialize the workspace configuration and permission storage.

    Args:
        working_dir: Workspace root directory.

    Returns:
        The effective configuration after initialization.
    """
    cfg = config.init(working_dir)
    PermissionManager(working_dir=working_dir, freeact_dir=working_dir / config.FREEACT_DIR_NAME).init()
    return cfg


async def run(namespace: argparse.Namespace) -> None:
    """Run the agent terminal interface.

    Loads configuration, creates the agent, and starts the interactive terminal.

    Args:
        namespace: Parsed CLI arguments.
    """
    working_dir = Path.cwd()
    cfg = await asyncio.to_thread(initialize, working_dir)
    if namespace.session_id is not None and not cfg.agent.enable_persistence:
        raise SystemExit("--session-id requires enable_persistence=true in .freeact/config.toml")

    runtime = config.resolve(cfg, working_dir)

    if runtime.ptc_servers:
        await generate_mcp_sources(runtime.ptc_servers, runtime.workspace.generated_dir)

    permissions = PermissionManager(working_dir=working_dir, freeact_dir=runtime.workspace.freeact_dir)
    await asyncio.to_thread(permissions.init)

    agent = Agent(
        runtime,
        session_id=str(namespace.session_id) if namespace.session_id is not None else None,
        sandbox=namespace.sandbox,
        sandbox_config=namespace.sandbox_config,
    )

    async with agent:
        app = TerminalApp(
            agent_id=agent.agent_id,
            stream=agent.stream,
            cancel=agent.cancel,
            skills_metadata=runtime.skills_metadata,
            terminal_config=cfg.terminal,
            permissions=permissions,
            skip_permissions=namespace.skip_permissions,
            working_dir=working_dir,
        )
        await app.run_async()


def main() -> None:
    """CLI entry point.

    Supports commands:
    - freeact: Run the agent (default)
    - freeact init: Initialize .freeact/ configuration directory
    """
    load_dotenv(find_dotenv(usecwd=True))
    namespace = parse_args()
    configure_logging(namespace.log_level)

    if namespace.command == "init":
        initialize(Path.cwd())
        logger.info("Ensured .freeact/ configuration directory")
        return

    asyncio.run(run(namespace))


if __name__ == "__main__":
    main()
