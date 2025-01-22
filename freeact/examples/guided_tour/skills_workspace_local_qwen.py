import asyncio

from freeact import CodeActAgent, QwenCoder, execution_environment
from freeact.examples.utils import stream_turn


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:example",
    ) as env:
        skill_sources = await env.executor.get_module_sources(
            [
                "freeact_skills.search.google.stream.api",
                "weather.weather_report",  # (1)!
            ],
        )

        model = QwenCoder(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model_name="qwen2.5-coder:32b-instruct-q8_0",
            skill_sources=skill_sources,
        )
        agent = CodeActAgent(model=model, executor=env.executor)

        turn = agent.run(
            "What are the top 3 cities to view the northern lights in Norway?"
            + " Add current temperature and cloud coverage for each location.",
        )
        await stream_turn(turn)


if __name__ == "__main__":
    asyncio.run(main())
