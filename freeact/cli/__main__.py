import asyncio
from pathlib import Path
from typing import Annotated, Any, Dict, List

import typer
from dotenv import load_dotenv
from rich.console import Console

from freeact import Claude, CodeActAgent, CodeActModel, Gemini, QwenCoder, execution_environment
from freeact.cli.utils import read_file, stream_conversation

app = typer.Typer()


async def amain(
    api_key: str | None,
    base_url: str | None,
    model_name: str,
    ipybox_tag: str,
    executor_key: str,
    workspace_path: Path,
    skill_modules: List[str] | None,
    system_extension: Path | None,
    log_file: Path,
    temperature: float,
    max_tokens: int,
    show_token_usage: bool,
    record_conversation: bool,
    record_path: Path,
):
    async with execution_environment(
        executor_key=executor_key,
        ipybox_tag=ipybox_tag,
        workspace_path=workspace_path,
        log_file=log_file,
    ) as env:
        skill_sources = await env.executor.get_module_sources(module_names=skill_modules)

        if system_extension:
            system_extension_str = await read_file(system_extension)
        else:
            system_extension_str = None

        run_kwargs: Dict[str, Any] = {}
        model: CodeActModel

        if "claude" in model_name.lower():
            model = Claude(
                model_name=model_name,  # type: ignore
                system_extension=system_extension_str,
                prompt_caching=True,
                logger=env.logger,
                api_key=api_key,
                base_url=base_url,
            )
            run_kwargs |= {
                "skill_sources": skill_sources,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        elif "gemini" in model_name.lower():
            model = Gemini(
                model_name=model_name,  # type: ignore
                skill_sources=skill_sources,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
            )
        elif "qwen" in model_name.lower():
            model = QwenCoder(
                model_name=model_name,
                skill_sources=skill_sources,
                api_key=api_key,
                base_url=base_url,
            )
            run_kwargs |= {
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        else:
            typer.echo(f"Unsupported model: {model_name}", err=True)
            raise typer.Exit(code=1)

        agent = CodeActAgent(model=model, executor=env.executor)

        if record_conversation:
            console = Console(record=True, width=120, force_terminal=True)
        else:
            console = Console()

        await stream_conversation(agent, console, **run_kwargs, show_token_usage=show_token_usage)

        if record_conversation:
            console.save_svg(str(record_path), title="")


@app.command()
def main(
    model_name: Annotated[str, typer.Option(help="Name of the model")] = "claude-3-5-sonnet-20241022",
    api_key: Annotated[str | None, typer.Option(help="API key of the model")] = None,
    base_url: Annotated[str | None, typer.Option(help="Base URL of the model")] = None,
    ipybox_tag: Annotated[str, typer.Option(help="Tag of the ipybox Docker image")] = "ghcr.io/gradion-ai/ipybox:basic",
    executor_key: Annotated[str, typer.Option(help="Key for private executor directories")] = "default",
    workspace_path: Annotated[Path, typer.Option(help="Path to the workspace directory")] = Path("workspace"),
    skill_modules: Annotated[List[str] | None, typer.Option(help="Skill modules to load")] = None,
    system_extension: Annotated[Path | None, typer.Option(help="Path to a system extension file")] = None,
    log_file: Annotated[Path, typer.Option(help="Path to the log file")] = Path("logs", "agent.log"),
    temperature: Annotated[float, typer.Option(help="Temperature for generating model responses")] = 0.0,
    max_tokens: Annotated[int, typer.Option(help="Maximum number of tokens for each model response")] = 4096,
    show_token_usage: Annotated[bool, typer.Option(help="Include token usage data in responses")] = False,
    record_conversation: Annotated[bool, typer.Option(help="Record conversation as SVG file")] = False,
    record_path: Annotated[Path, typer.Option(help="Path to the SVG file")] = Path("conversation.svg"),
):
    asyncio.run(amain(**locals()))


if __name__ == "__main__":
    load_dotenv()
    app()
