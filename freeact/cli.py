import argparse
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv
from ipybox.utils import arun
from rich.console import Console

from freeact.agent import Agent
from freeact.agent.config import Config, init_config
from freeact.agent.tools.pytools.apigen import generate_mcp_sources
from freeact.terminal import Terminal
from freeact.terminal.recording import save_conversation


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the freeact CLI."""
    parser = argparse.ArgumentParser(
        prog="freeact",
        description="Run the freeact code action agent",
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
        "--record",
        action="store_true",
        help="Record conversation as SVG and HTML files",
    )
    parser.add_argument(
        "--record-dir",
        type=Path,
        default=Path("output"),
        metavar="PATH",
        help="Path to the recording output directory",
    )
    parser.add_argument(
        "--record-title",
        type=str,
        default="Conversation",
        help="Title of the recording",
    )
    return parser


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Arguments to parse. Uses `sys.argv` if `None`.
    """
    parser = create_parser()
    return parser.parse_args(args)


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


def create_config() -> Config:
    """Initialize and load configuration from `.freeact/` directory."""
    init_config()
    return Config()


async def run(namespace: argparse.Namespace) -> None:
    """Run the agent terminal interface.

    Loads configuration, creates the agent, and starts the interactive
    terminal. Optionally records the conversation to SVG/HTML.

    Args:
        namespace: Parsed CLI arguments.
    """
    if namespace.record:
        console = Console(record=True, width=120, force_terminal=True)
    else:
        console = None

    config: Config = await arun(create_config)
    agent = Agent(
        model=config.model,
        model_settings=config.model_settings,
        system_prompt=config.system_prompt,
        mcp_servers=config.mcp_servers,
        sandbox=namespace.sandbox,
        sandbox_config=namespace.sandbox_config,
    )

    if config.ptc_servers:
        await generate_mcp_sources(config.ptc_servers)

    terminal = Terminal(agent=agent, console=console)
    await terminal.run()

    if namespace.record and console is not None:
        await save_conversation(
            console=console,
            record_dir=namespace.record_dir,
            record_title=namespace.record_title,
        )


def main(args: list[str] | None = None) -> None:
    """CLI entry point.

    Loads environment variables, configures logging, and runs the agent.

    Args:
        args: CLI arguments. Uses `sys.argv` if `None`.
    """
    load_dotenv()
    namespace = parse_args(args)
    configure_logging(namespace.log_level)
    asyncio.run(run(namespace))


if __name__ == "__main__":
    main()
