import asyncio
from pathlib import Path

from aioconsole import ainput
from dotenv import load_dotenv

from examples.agent.utils import dotenv_variables, execution_environment
from freeact import (
    Claude,
    ClaudeModelName,
    CodeActAgent,
    CodeAction,
    CodeActModelTurn,
)


async def conversation(agent: CodeActAgent, skill_sources: str):
    while True:
        user_message = await ainput("User: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        agent_turn = agent.run(
            user_message,
            skill_sources=skill_sources,
            temperature=0.0,
            max_tokens=4096,
        )

        async for activity in agent_turn.stream():
            match activity:
                case CodeActModelTurn() as turn:
                    print("Agent response:")
                    async for s in turn.stream():
                        print(s, end="", flush=True)
                    print()

                    resp = await turn.response()
                    if resp.code is not None:
                        print("\n```python")
                        print(resp.code)
                        print("```\n")

                case CodeAction() as act:
                    print("Execution result:")
                    async for s in act.stream():
                        print(s, end="", flush=True)
                    print()


async def main(
    model_name: ClaudeModelName,
    workspace_key: str,
    workspace_path: Path = Path("workspace"),
    ipybox_tag: str = "gradion-ai/ipybox-all",
    env_vars: dict[str, str] = dotenv_variables(),
    log_file: Path | str = Path("logs", "agent.log"),
    system_extension: str | None = None,
    skill_modules: list[str] = [
        "freeact_skills.search.perplexity.api",
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
        await conversation(agent, skill_sources=skill_sources)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(model_name="claude-3-5-haiku-20241022", workspace_key="example"))
