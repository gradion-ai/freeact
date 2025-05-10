import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict

from aioconsole import ainput
from PIL import Image

from freeact import (
    CodeActAgent,
    CodeActAgentResponse,
    CodeActAgentTurn,
    CodeActModelTurn,
    CodeActModelUsage,
    CodeExecution,
)


# --8<-- [start:stream_conversation]
async def stream_conversation(agent: CodeActAgent, **kwargs):
    usage = CodeActModelUsage()

    while True:
        user_message = await ainput("User message: ")

        if user_message.lower() == "q":
            break

        agent_turn = agent.run(user_message, **kwargs)
        await stream_turn(agent_turn)

        agent_response = await agent_turn.response()
        usage.update(agent_response.usage)  # (4)!

        print("Accumulated usage:")
        print(json.dumps(asdict(usage), indent=2))
        print()


# --8<-- [end:stream_conversation]


# --8<-- [start:stream_turn]
async def stream_turn(agent_turn: CodeActAgentTurn):
    produced_images: Dict[Path, Image.Image] = {}

    async for activity in agent_turn.stream():
        match activity:
            case CodeActModelTurn() as turn:
                print("Model response:")
                async for s in turn.stream():
                    print(s, end="", flush=True)
                print()

                response = await turn.response()  # (1)!
                if response.code:  # (2)!
                    print("\n```python")
                    print(response.code)
                    print("```\n")

            case CodeExecution() as execution:
                print("Execution result:")
                async for s in execution.stream():
                    print(s, end="", flush=True)
                result = await execution.result()  # (3)!
                produced_images.update(result.images)
                print()

    if produced_images:
        print("\n\nProduced images:")
    for path in produced_images.keys():
        print(str(path))


# --8<-- [end:stream_turn]


# --8<-- [start:final_response]
async def final_response(agent: CodeActAgent, user_message: str) -> str:
    turn: CodeActAgentTurn = agent.run(user_message)
    resp: CodeActAgentResponse = await turn.response()  # (1)!
    return resp.text


# --8<-- [end:final_response]
