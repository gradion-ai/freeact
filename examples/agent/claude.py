import asyncio
from pathlib import Path
from typing import List

from aioconsole import ainput
from dotenv import dotenv_values, load_dotenv

from freeact import (
    Claude,
    ClaudeModelName,
    CodeActAgent,
    CodeActContainer,
    CodeActExecutor,
    CodeAction,
    CodeActModelTurn,
)
from freeact.logger import Logger
from freeact.skills import SkillInfo, get_skill_infos

RUNBOOK = """Your overall workflow instructions (= runbook):
- Start answering an initial user query
- In your final answer to the user query, additionally suggest 3 follow up actions the user can take
- Let the user choose one of the follow up actions or choose another action if none of the follow up actions are relevant
- If the initial query or a follow-up action is related to the weather in a given city, output the current temperature in the city multiplied by 3.17.
- After sharing your reasoning in <thinking> tags, you MUST ask the user for feedback.
  - do not generate and execute code yet at this point.
  - the user may either confirm your reasoning and let you proceed with generating code
  - or ask you to modify your reasoning and reasoning steps based on their feedback
- Repeat the overall workflow with the chosen follow up action
"""


async def conversation(agent: CodeActAgent, skill_infos: List[SkillInfo]):
    while True:
        user_message = await ainput("User: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        agent_call = agent.run(user_message, skill_infos=skill_infos, temperature=0.0, max_tokens=4096)
        async for activity in agent_call.stream():
            match activity:
                case CodeActModelTurn() as turn:
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


async def main(
    model_name: ClaudeModelName,
    log_file: Path,
    prompt_caching: bool = True,
    use_runbook: bool = False,
):
    # environment variables for the container
    env = {k: v for k, v in dotenv_values().items() if v is not None}

    async with CodeActContainer(tag="gradion/ipybox-incubator", env=env) as container:
        async with CodeActExecutor(
            key="123", host="localhost", port=container.port, workspace=container.workspace
        ) as executor:
            async with Logger(file=log_file) as logger:
                skill_modules = [
                    "freeact.skills.search.web.api",
                    "freeact.skills.zotero.api",
                    "freeact.skills.reader.api",
                ]
                skill_infos = get_skill_infos(skill_modules, executor.skill_paths)

                model = Claude(
                    model_name=model_name,
                    system_extension=RUNBOOK if use_runbook else None,
                    prompt_caching=prompt_caching,
                    logger=logger,
                )
                agent = CodeActAgent(model=model, executor=executor)
                await conversation(agent, skill_infos=skill_infos)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(
        main(
            model_name="claude-3-5-sonnet-20241022",
            log_file=Path("logs", "agent.log"),
            prompt_caching=False,
            use_runbook=False,
        )
    )