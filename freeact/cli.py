import argparse
import asyncio
import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv

from freeact.agent import Agent
from freeact.agent.config import Config as AgentConfig
from freeact.agent.store import SessionStore
from freeact.terminal import Config as TerminalConfig
from freeact.terminal import TerminalInterface
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


async def create_config() -> tuple[AgentConfig, TerminalConfig]:
    """Load config from `.freeact/` or create and save defaults on first run."""

    agent_config = await AgentConfig.init()
    terminal_config = await TerminalConfig.init(working_dir=agent_config.working_dir)
    return agent_config, terminal_config


async def run(namespace: argparse.Namespace) -> None:
    """Run the agent terminal interface.

    Loads configuration, creates the agent, and starts the interactive terminal.

    Args:
        namespace: Parsed CLI arguments.
    """
    agent_config, terminal_config = await create_config()
    session_id = str(namespace.session_id or uuid.uuid4())
    session_store = SessionStore(agent_config.sessions_dir, session_id)
    agent = Agent(
        config=agent_config,
        sandbox=namespace.sandbox,
        sandbox_config=namespace.sandbox_config,
        session_store=session_store,
    )

    if agent_config.ptc_servers:
        await generate_mcp_sources(agent_config.ptc_servers, agent_config.generated_dir)

    terminal = TerminalInterface(agent=agent, config=terminal_config)
    await terminal.run()


def main() -> None:
    """CLI entry point.

    Supports commands:
    - freeact: Run the agent (default)
    - freeact init: Initialize .freeact/ configuration directory
    """
    load_dotenv()
    namespace = parse_args()
    configure_logging(namespace.log_level)

    if namespace.command == "init":
        asyncio.run(create_config())
        logger.info("Ensured .freeact/ configuration directory")
        return

    asyncio.run(run(namespace))


if __name__ == "__main__":
    main()
