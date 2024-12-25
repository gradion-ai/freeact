import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Annotated, List

import typer
from dotenv import load_dotenv

from freeact import Claude, CodeActAgent, Gemini
from freeact.cli.utils import execution_environment, read_file, stream_conversation

app = typer.Typer()


class ModelName(StrEnum):
    CLAUDE_3_5_SONNET_20241022 = "claude-3-5-sonnet-20241022"
    CLAUDE_3_5_HAIKU_20241022 = "claude-3-5-haiku-20241022"
    GEMINI_2_0_FLASH_EXP = "gemini-2.0-flash-exp"


async def amain(
    model_name: ModelName,
    ipybox_tag: str,
    executor_key: str,
    workspace_path: Path,
    skill_modules: List[str] | None,
    system_extension: Path | None,
    log_file: Path,
    temperature: float,
    max_tokens: int,
):
    async with execution_environment(
        executor_key=executor_key,
        ipybox_tag=ipybox_tag,
        workspace_path=workspace_path,
        log_file=log_file,
    ) as (executor, logger):
        skill_sources = await executor.get_module_sources(module_names=skill_modules)

        if system_extension:
            system_extension_str = await read_file(system_extension)
        else:
            system_extension_str = None

        if model_name == ModelName.GEMINI_2_0_FLASH_EXP:
            model = Gemini(
                model_name=model_name,  # type: ignore
                skill_sources=skill_sources,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            model = Claude(
                model_name=model_name,  # type: ignore
                system_extension=system_extension_str,
                prompt_caching=True,
                logger=logger,
            )
        agent = CodeActAgent(model=model, executor=executor)

        if model_name == ModelName.GEMINI_2_0_FLASH_EXP:
            await stream_conversation(agent)
        else:
            await stream_conversation(
                agent,
                skill_sources=skill_sources,
                temperature=temperature,
                max_tokens=max_tokens,
            )


@app.command()
def main(
    model_name: ModelName = ModelName.CLAUDE_3_5_SONNET_20241022,
    ipybox_tag: Annotated[str, typer.Option(help="Tag of the ipybox Docker image")] = "gradion-ai/ipybox-default",
    executor_key: Annotated[str, typer.Option(help="Key for private executor directories")] = "default",
    workspace_path: Annotated[Path, typer.Option(help="Path to the workspace directory")] = Path("workspace"),
    skill_modules: Annotated[List[str] | None, typer.Option(help="Skill modules to load")] = None,
    system_extension: Annotated[Path | None, typer.Option(help="Path to a system extension file")] = None,
    log_file: Annotated[Path, typer.Option(help="Path to the log file")] = Path("logs", "agent.log"),
    temperature: Annotated[float, typer.Option(help="Temperature for generating model responses")] = 0.0,
    max_tokens: Annotated[int, typer.Option(help="Maximum number of tokens for each model response")] = 4096,
):
    asyncio.run(amain(**locals()))


if __name__ == "__main__":
    load_dotenv()
    app()
