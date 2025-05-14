import asyncio
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, List

import typer
from rich.console import Console

from freeact import (
    CodeActAgent,
    LiteCodeActModel,
    execution_environment,
)
from freeact.cli.utils import read_file, save_conversation, stream_conversation


class ReasoningEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


app = typer.Typer()


async def amain(
    model_name: str,
    api_key: str | None,
    base_url: str | None,
    use_executor_tool: bool | None,
    use_editor_tool: bool | None,
    system_template: Path | None,
    skill_modules: List[str] | None,
    mcp_servers: Path | None,
    reasoning_effort: ReasoningEffort | None,
    temperature: float | None,
    max_tokens: int,
    show_token_usage: bool,
    ipybox_tag: str,
    workspace_path: Path,
    workspace_key: str,
    record_conversation: bool,
    record_dir: Path,
    record_title: str,
):
    if system_template:
        system_template_str = await read_file(system_template)
    else:
        system_template_str = None

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

                if "mcpTools" in server_params_dict:
                    tool_names = server_params_dict["mcpTools"]
            else:
                tool_names = {}

            if skill_modules or tool_names:
                skill_sources = await provider.get_sources(module_names=skill_modules, mcp_tool_names=tool_names)
            else:
                skill_sources = None

        model = LiteCodeActModel(
            model_name=model_name,
            skill_sources=skill_sources,
            system_template=system_template_str,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
            max_tokens=max_tokens,
            use_executor_tool=use_executor_tool,
            use_editor_tool=use_editor_tool,
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
            await save_conversation(console, record_dir=record_dir, record_title=record_title)


@app.command()
def main(
    model_name: Annotated[str, typer.Option(help="Name of the model")] = "anthropic/claude-3-7-sonnet-20250219",
    api_key: Annotated[str | None, typer.Option(help="API key for the model")] = None,
    base_url: Annotated[str | None, typer.Option(help="Base URL of the model provider")] = None,
    use_executor_tool: Annotated[
        bool | None, typer.Option(help="Use the builtin executor tool for code action generation")
    ] = None,
    use_editor_tool: Annotated[
        bool | None, typer.Option(help="Use the builtin editor tool for code action editing")
    ] = None,
    system_template: Annotated[Path | None, typer.Option(help="Path to a custom system template")] = None,
    skill_modules: Annotated[List[str] | None, typer.Option(help="Skill modules to load")] = None,
    mcp_servers: Annotated[Path | None, typer.Option(help="MCP servers to register")] = None,
    reasoning_effort: Annotated[ReasoningEffort | None, typer.Option(help="Reasoning effort of the model")] = None,
    temperature: Annotated[float | None, typer.Option(help="Temperature for generating model responses")] = None,
    max_tokens: Annotated[int, typer.Option(help="Maximum number of tokens for each model response")] = 8192,
    show_token_usage: Annotated[bool, typer.Option(help="Show accumulated token usage and costs")] = True,
    ipybox_tag: Annotated[
        str, typer.Option(help="Name and tag of the ipybox Docker image")
    ] = "ghcr.io/gradion-ai/ipybox:basic",
    workspace_path: Annotated[Path, typer.Option(help="Path to the workspace directory")] = Path("workspace"),
    workspace_key: Annotated[str, typer.Option(help="Key for private workspace directories")] = "default",
    record_conversation: Annotated[bool, typer.Option(help="Record conversation as SVG and HTML files")] = False,
    record_dir: Annotated[Path, typer.Option(help="Path to the recording output directory")] = Path("output"),
    record_title: Annotated[str, typer.Option(help="Title of the recording")] = "Conversation",
):
    asyncio.run(amain(**locals()))
