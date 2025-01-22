import asyncio

from freeact import Claude, CodeActAgent, execution_environment
from freeact.examples.utils import stream_turn

SYSTEM_EXTENSIONS = """
Your overall workflow instructions (= runbook):
- Start answering an initial user query
- In your final answer to the user query, additionally suggest 3 follow up
  actions the user can take
- Let the user choose one of the follow up actions or choose another action
  if none of the follow up actions are relevant
- Repeat the overall workflow with the chosen follow up action

Domain-specific rules:
- Report temperatures in Kelvin
- Report cloud coverage in low (0-30%), medium (30-70%), or high (70-100%)
"""


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:example",
    ) as env:
        model = Claude(
            model_name="claude-3-5-sonnet-20241022",
            system_extension=SYSTEM_EXTENSIONS,  # (1)!
            logger=env.logger,
        )
        agent = CodeActAgent(model=model, executor=env.executor)

        skill_sources = await env.executor.get_module_sources(
            [
                "freeact_skills.search.google.stream.api",
                "weather.weather_report",
            ],
        )

        turn = agent.run(
            "What are the top 3 cities to view the northern lights in Norway?"
            + " Add current temperature and cloud coverage for each location.",
            skill_sources=skill_sources,
        )
        await stream_turn(turn)


if __name__ == "__main__":
    asyncio.run(main())
