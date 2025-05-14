import platform
from pathlib import Path
from typing import Dict

import aiofiles
import prefixed
import prompt_toolkit
from PIL import Image
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text

from freeact import (
    CodeActAgent,
    CodeActAgentTurn,
    CodeActModelTurn,
    CodeActModelUsage,
    CodeExecution,
)

CONVERSATION_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
{svg}
</body>
</html>
"""


async def save_conversation(console: Console, record_dir: Path, record_title: str):
    from freeact.environment import arun

    record_dir.mkdir(parents=True, exist_ok=True)

    record_svg_path = record_dir / "conversation.svg"
    record_html_path = record_dir / "conversation.html"

    await arun(console.save_svg, str(record_svg_path), title=record_title)

    async with aiofiles.open(record_svg_path, "r") as file:
        svg = await file.read()

    async with aiofiles.open(record_html_path, "w") as file:
        await file.write(CONVERSATION_HTML_TEMPLATE.format(title=record_title, svg=svg))


async def stream_conversation(agent: CodeActAgent, console: Console, show_token_usage: bool = True, **kwargs):
    "enter"
    empty_input = False

    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        """Submit the input when Enter is pressed."""
        event.app.exit(result=event.app.current_buffer.text)

    @kb.add("escape", "enter")
    def _(event):
        """Insert a newline when Alt+Enter or Meta+Enter is pressed."""
        event.current_buffer.insert_text("\n")

    session = prompt_toolkit.PromptSession(
        multiline=True,
        key_bindings=kb,
    )

    escape_key = "Option" if platform.system() == "Darwin" else "Alt"
    usage = CodeActModelUsage()

    while True:
        console.print(Rule("User message", style="dodger_blue1", characters="━"))

        if empty_input:
            empty_input = False
            prefix = "Please enter a non-empty message"
        else:
            prefix = ""

        input_prompt = f"'q': quit, {escape_key}+Enter: newline\n\n{prefix}> "
        user_message = await session.prompt_async(input_prompt)

        if not user_message.strip():
            empty_input = True
            continue

        if console.record:
            console.print(input_prompt, highlight=False, end="")
            console.print(user_message, highlight=False)

        if user_message.lower() == "q":
            break

        agent_turn = agent.run(user_message, **kwargs)
        await stream_turn(agent_turn, console, usage, show_token_usage)


async def stream_turn(
    agent_turn: CodeActAgentTurn, console: Console, usage: CodeActModelUsage, show_token_usage: bool = False
):
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
                usage.update(response.usage)

                if console.record:
                    # needed to wrap text in SVG output
                    console.print(response.text, highlight=False)
                    console.print()

                if response.code:
                    syntax = Syntax(response.code, "python", theme="monokai", line_numbers=True)
                    panel = Panel(syntax, title="Code action", title_align="left", style="yellow")
                    console.print(panel)
                    console.print()

                if show_token_usage:
                    token_usage = [
                        f"input={format_token_count(usage.input_tokens)}",
                        f"thinking={format_token_count(usage.thinking_tokens)}",
                        f"output={format_token_count(usage.output_tokens)}",
                        f"cache_write={format_token_count(usage.cache_write_tokens)}",
                        f"cache_read={format_token_count(usage.cache_read_tokens)}",
                    ]
                    usage_str = f'Accumulated token usage: {", ".join(token_usage)}'
                    costs_str = f"Accumulated costs: {format_cost(usage.cost)}"

                    console.print()
                    console.print(f"{usage_str}; {costs_str}", highlight=False, style="grey50")

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


def format_token_count(n: int) -> str:
    return str(n) if n < 1000 else f"{prefixed.Float(n):.2h}"


def format_cost(cost: float | None) -> str:
    return "unknown" if cost is None else f"{cost:.3f} USD"


async def read_file(path: Path | str) -> str:
    async with aiofiles.open(Path(path), "r") as file:
        return await file.read()
