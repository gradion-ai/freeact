import asyncio
from pathlib import Path

from dotenv import load_dotenv

from examples.agent.utils import dotenv_variables, execution_environment, stream_conversation
from freeact import Claude, ClaudeModelName, CodeActAgent


async def main(
    model_name: ClaudeModelName,
    workspace_key: str,
    workspace_path: Path = Path("workspace"),
    ipybox_tag: str = "gradion-ai/ipybox-all",
    env_vars: dict[str, str] = dotenv_variables(),
    log_file: Path | str = Path("logs", "agent.log"),
    system_extension: str | None = None,
    skill_modules: list[str] = [
        "freeact_skills.search.google.stream.api",
        "freeact_skills.zotero.api",
        "freeact_skills.reader.api",
    ],
):
    async with execution_environment(
        workspace_key=workspace_key,
        workspace_path=workspace_path,
        ipybox_tag=ipybox_tag,
        env_vars=env_vars,
        log_file=log_file,
    ) as (executor, logger):
        skill_sources = await executor.get_module_sources(skill_modules)

        model = Claude(
            model_name=model_name,
            system_extension=system_extension,
            prompt_caching=True,
            logger=logger,
        )
        agent = CodeActAgent(model=model, executor=executor)
        await stream_conversation(agent, skill_sources=skill_sources)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(model_name="claude-3-5-haiku-20241022", workspace_key="example"))
