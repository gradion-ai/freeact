import asyncio

from freeact import CodeActAgent, QwenCoder, execution_environment
from freeact.examples.utils import stream_turn


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:example",
    ) as env:
        model = QwenCoder(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model_name="qwen2.5-coder:32b-instruct-q8_0",
        )
        agent = CodeActAgent(model=model, executor=env.executor)

        turn = agent.run("Calculate the square root of 1764")
        await stream_turn(turn)


if __name__ == "__main__":
    asyncio.run(main())
