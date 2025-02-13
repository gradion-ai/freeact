from pathlib import Path
from typing import Dict

from aioconsole import ainput
from PIL import Image

from freeact import (
    CodeActAgent,
    CodeActAgentTurn,
    CodeActModelTurn,
    CodeExecution,
)


# --8<-- [start:stream_conversation]
async def stream_conversation(agent: CodeActAgent, **kwargs):
    while True:
        user_message = await ainput("User message: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        agent_turn = agent.run(user_message, **kwargs)
        await stream_turn(agent_turn)


# --8<-- [end:stream_conversation]


# --8<-- [start:stream_turn]
async def stream_turn(agent_turn: CodeActAgentTurn):
    produced_images: Dict[Path, Image.Image] = {}

    async for activity in agent_turn.stream():
        match activity:
            case CodeActModelTurn() as turn:
                print("Agent response:")
                async for s in turn.stream():
                    print(s, end="", flush=True)
                print()

                response = await turn.response()
                if response.code:
                    print("\n```python")
                    print(response.code)
                    print("```\n")

            case CodeExecution() as execution:
                print("Execution result:")
                async for s in execution.stream():
                    print(s, end="", flush=True)
                result = await execution.result()
                produced_images.update(result.images)
                print()

    if produced_images:
        print("\n\nProduced images:")
    for path in produced_images.keys():
        print(str(path))


# --8<-- [end:stream_turn]
