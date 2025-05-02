import asyncio
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, List

import typer
from dotenv import load_dotenv
from rich.console import Console

from freeact import (
    CodeActAgent,
    LiteCodeActModel,
    execution_environment,
)
from freeact.cli.utils import read_file, stream_conversation


class ReasoningEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


app = typer.Typer()


async def amain(
    api_key: str | None,
    base_url: str | None,
    model_name: str,
    ipybox_tag: str,
    workspace_path: Path,
    workspace_key: str,
    skill_modules: List[str] | None,
    tool_use: bool | None,
    mcp_servers: Path | None,
    temperature: float | None,
    max_tokens: int,
    reasoning_effort: ReasoningEffort | None,
    show_token_usage: bool,
    record_conversation: bool,
    record_path: Path,
):
    async with execution_environment(
        ipybox_tag=ipybox_tag,
        workspace_path=workspace_path,
        workspace_key=workspace_key,
    ) as env:
        async with env.code_provider() as provider:
            if mcp_servers:
                server_params = await read_file(mcp_servers)
                server_params_dict = json.loads(server_params)
                tool_names = await provider.register_mcp_servers(server_params_dict["mcpServers"])
            else:
                tool_names = {}

            if skill_modules or tool_names:
                skill_sources = await provider.get_sources(module_names=skill_modules, mcp_tool_names=tool_names)
            else:
                skill_sources = None

        model = LiteCodeActModel(
            model_name=model_name,
            skill_sources=skill_sources,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
            max_tokens=max_tokens,
            tool_use=tool_use,
            api_key=api_key,
            base_url=base_url,
        )

        if record_conversation:
            console = Console(record=True, width=120, force_terminal=True)
        else:
            console = Console()

        async with env.code_executor() as executor:
            agent = CodeActAgent(model=model, executor=executor)
            await stream_conversation(agent, console, show_token_usage=show_token_usage)

        if record_conversation:
            console.save_svg(str(record_path), title="")


@app.command()
def main(
    model_name: Annotated[str, typer.Option(help="Name of the model")] = "anthropic/claude-3-5-sonnet-20241022",
    api_key: Annotated[str | None, typer.Option(help="API key of the model")] = None,
    base_url: Annotated[str | None, typer.Option(help="Base URL of the model")] = None,
    ipybox_tag: Annotated[str, typer.Option(help="Tag of the ipybox Docker image")] = "ghcr.io/gradion-ai/ipybox:basic",
    workspace_path: Annotated[Path, typer.Option(help="Path to the workspace directory")] = Path("workspace"),
    workspace_key: Annotated[str, typer.Option(help="Key for private workspace directories")] = "default",
    skill_modules: Annotated[List[str] | None, typer.Option(help="Skill modules to load")] = None,
    tool_use: Annotated[bool | None, typer.Option(help="Use tools for code action generation")] = None,
    mcp_servers: Annotated[Path | None, typer.Option(help="Path to a MCP servers file")] = None,
    temperature: Annotated[float | None, typer.Option(help="Temperature for generating model responses")] = None,
    max_tokens: Annotated[int, typer.Option(help="Maximum number of tokens for each model response")] = 8192,
    reasoning_effort: Annotated[ReasoningEffort | None, typer.Option(help="Reasoning effort for the model")] = None,
    show_token_usage: Annotated[bool, typer.Option(help="Include token usage data in responses")] = True,
    record_conversation: Annotated[bool, typer.Option(help="Record conversation as SVG file")] = False,
    record_path: Annotated[Path, typer.Option(help="Path to the SVG file")] = Path("conversation.svg"),
):
    asyncio.run(amain(**locals()))


if __name__ == "__main__":
    load_dotenv()
    app()
