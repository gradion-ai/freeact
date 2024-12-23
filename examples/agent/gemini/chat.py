import asyncio
from pathlib import Path

from dotenv import load_dotenv

from examples.agent.utils import conversation, dotenv_variables, execution_environment
from freeact import CodeActAgent, Gemini, GeminiModelName


async def main(
    model_name: GeminiModelName,
    workspace_key: str,
    workspace_path: Path = Path("workspace"),
    ipybox_tag: str = "gradion-ai/ipybox-all",
    env_vars: dict[str, str] = dotenv_variables(),
    log_file: Path | str = Path("logs", "agent.log"),
    skill_modules: list[str] = [
        "freeact_skills.search.google.api",
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
    ) as (executor, _):
        skill_sources = await executor.get_module_sources(skill_modules)

        model = Gemini(model_name=model_name, skill_sources=skill_sources)
        agent = CodeActAgent(model=model, executor=executor)
        await conversation(agent)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(model_name="gemini-2.0-flash-thinking-exp-1219", workspace_key="example"))
