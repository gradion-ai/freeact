import asyncio
from pathlib import Path

from aioconsole import ainput
from dotenv import dotenv_values, load_dotenv
from gradion.executor import ExecutionClient, ExecutionContainer

from gradion_incubator.codeact import AssistantMessage, ClaudeCodeActModel, ClaudeModelName, CodeActAgent, Stage
from gradion_incubator.logger import Logger

CLEANUP_CODE = """
import os
import shutil

from pathlib import Path

generated_dir = Path('generated')
if generated_dir.exists():
    for item in generated_dir.iterdir():
        if item.is_file() and item.name != "__init__.py":
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
"""


async def conversation(agent: CodeActAgent):
    while True:
        user_message = await ainput("User: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        async for chunk in agent.run(user_message):
            match chunk:
                case Stage() as stage:
                    print("\n")
                    print(f"Stage = {stage.value}:")
                case AssistantMessage():
                    print("\n")
                case str():
                    print(chunk, end="", flush=True)


async def main(model_name: ClaudeModelName, log_file: Path, prompt_caching: bool = True):
    # environment variables for the container
    env = {k: v for k, v in dotenv_values().items() if v is not None}

    # bind mounts for the container
    binds = {
        "gradion_incubator": "gradion_incubator",
        "generated": "generated",
    }

    async with ExecutionContainer(tag="gradion/executor-successor", binds=binds, env=env) as container:
        async with ExecutionClient(host="localhost", port=container.port) as executor:
            await executor.execute("%load_ext autoreload")
            await executor.execute("%autoreload 2")
            await executor.execute("from gradion_incubator.components.editor import file_editor")
            await executor.execute("import sys; sys.path.append('generated')")
            # await executor.execute(CLEANUP_CODE)

            async with Logger(file=log_file) as logger:
                files_root = Path("gradion_incubator", "components")
                files = [
                    # files_root / "search" / "internet.py",
                    files_root / "zotero" / "api.py",
                    files_root / "reader" / "api.py",
                ]

                generated_interface_path = Path("generated", "foo", "interface.py")

                if generated_interface_path.exists():
                    files.append(generated_interface_path)

                model = ClaudeCodeActModel(
                    model_name=model_name,
                    prompt_caching=prompt_caching,
                    python_files=files,
                    logger=logger,
                )
                agent = CodeActAgent(model=model, executor=executor)
                await conversation(agent)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(model_name="claude-3-5-haiku-20241022", log_file=Path("logs", "agent.log")))
