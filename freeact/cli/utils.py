from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

import aiofiles
from dotenv import dotenv_values
from ipybox import arun
from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text

from freeact import (
    CodeActAgent,
    CodeActAgentTurn,
    CodeActModelTurn,
    CodeExecution,
    CodeExecutionContainer,
    CodeExecutor,
)
from freeact.logger import Logger


def dotenv_variables() -> dict[str, str]:
    return {k: v for k, v in dotenv_values().items() if v is not None}


@asynccontextmanager
async def execution_environment(
    executor_key: str = "default",
    ipybox_tag: str = "ghcr.io/gradion-ai/ipybox:minimal",
    env_vars: dict[str, str] = dotenv_variables(),
    workspace_path: Path | str = Path("workspace"),
    log_file: Path | str = Path("logs", "agent.log"),
):
    async with CodeExecutionContainer(
        tag=ipybox_tag,
        env=env_vars,
        workspace_path=workspace_path,
    ) as container:
        async with CodeExecutor(
            key=executor_key,
            port=container.port,
            workspace=container.workspace,
        ) as executor:
            async with Logger(file=log_file) as logger:
                yield executor, logger


async def stream_conversation(agent: CodeActAgent, console: Console, show_token_usage: bool = False, **kwargs):
    while True:
        console.print(Rule("User message", style="dodger_blue1", characters="━"))
        user_message = await arun(Prompt.ask, "('q' to quit)", console=console)

        if console.record:
            console.print(user_message, highlight=False)

        if user_message.lower() == "q":
            break

        agent_turn = agent.run(user_message, **kwargs)
        await stream_turn(agent_turn, console, show_token_usage)


async def stream_turn(agent_turn: CodeActAgentTurn, console: Console, show_token_usage: bool = False):
    produced_images: Dict[Path, Image.Image] = {}

    async for activity in agent_turn.stream():
        match activity:
            case CodeActModelTurn() as turn:
                console.print(Rule("Model response", style="green", characters="━"))

                if not console.record:
                    async for s in turn.stream():
                        console.print(s, end="", highlight=False)
                    console.print("\n")

                response = await turn.response()

                if console.record:
                    # needed to wrap text in SVG output
                    console.print(response.text, highlight=False)
                    console.print()

                if response.code:
                    syntax = Syntax(response.code, "python", theme="monokai", line_numbers=True)
                    panel = Panel(syntax, title="Code action", title_align="left", style="yellow")
                    console.print(panel)
                    console.print()

                if show_token_usage and response.token_usage:
                    token_usage_str = ", ".join(f"{k}={v}" for k, v in response.token_usage.items())
                    console.print()
                    console.print(f"\[{token_usage_str}]", highlight=False, style="grey23")

            case CodeExecution() as execution:
                console.print(Rule("Execution result", style="white", characters="━"))

                if not console.record:
                    async for s in execution.stream():
                        r = Text.from_ansi(s, style="navajo_white3")
                        console.print(r, end="")

                result = await execution.result()

                if console.record:
                    r = Text.from_ansi(result.text, style="navajo_white3")
                    console.print(r)

                produced_images.update(result.images)
                console.print()

    if produced_images:
        paths_str = "\n".join(str(path) for path in produced_images.keys())
        panel = Panel(paths_str, title="Produced images", title_align="left", style="magenta")
        console.print(panel)


async def read_file(path: Path | str) -> str:
    async with aiofiles.open(Path(path), "r") as file:
        return await file.read()
