from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import dotenv_values

from freeact import (
    CodeActContainer,
    CodeActExecutor,
)
from freeact.logger import Logger


def dotenv_variables() -> dict[str, str]:
    return {k: v for k, v in dotenv_values().items() if v is not None}


@asynccontextmanager
async def execution_environment(
    workspace_key: str,
    workspace_path: Path,
    ipybox_tag: str,
    env_vars: dict[str, str],
    log_file: Path | str,
):
    async with CodeActContainer(
        tag=ipybox_tag,
        env=env_vars,
        workspace_path=workspace_path,
    ) as container:
        async with CodeActExecutor(
            key=workspace_key,
            port=container.port,
            workspace=container.workspace,
        ) as executor:
            async with Logger(file=log_file) as logger:
                yield executor, logger
