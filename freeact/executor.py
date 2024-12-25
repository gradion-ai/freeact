from dataclasses import dataclass
from pathlib import Path
from typing import List

from ipybox import ExecutionClient, ExecutionContainer, arun


@dataclass
class Workspace:
    """Represents a workspace containing shared and private agent skills. These
    are skills that are not pre-installed in the code execution container.

    Workspaces are bind-mounted into `CodeExecutionContainer` to share skills between
    a code execution container and the host machine.

    Args:
        path: Base path of the workspace directory structure on the host.
    """

    path: Path

    @property
    def private_skills_path(self) -> Path:
        """Path to private skills root directory."""
        return self.path / "skills" / "private"

    @property
    def shared_skills_path(self) -> Path:
        """Path to shared skills directory."""
        return self.path / "skills" / "shared"


class CodeExecutionContainer(ExecutionContainer):
    """Context manager for managing code execution container lifecycle.

    Extends `ipybox`'s `ExecutionContainer` to provide workspace-specific bind mounts for skill directories.
    Handles creation, port mapping, volume binding, and cleanup of the container.

    Args:
        tag: Docker image tag to use for the container
        env: Optional environment variables to set in the container
        port: Optional host port to map to container's executor port. Random port used if not specified
        workspace_path: Optional path to workspace directory, defaults to "workspace"

    Example:
        ```python
        async with CodeExecutionContainer(tag="gradion-ai/ipybox-example", workspace_path=Path("workspace")) as container:
            # Container is running and available at container.port
            ...
        # Container is automatically cleaned up after context exit
        ```
    """

    def __init__(
        self,
        tag: str,
        env: dict[str, str] | None = None,
        port: int | None = None,
        workspace_path: Path | str | None = None,
    ):
        self.workspace = Workspace(Path(workspace_path) if workspace_path else Path("workspace"))

        binds = {
            self.workspace.private_skills_path: "skills/private",
            self.workspace.shared_skills_path: "skills/shared",
        }

        super().__init__(tag=tag, binds=binds, env=env, port=port)


class CodeExecutor(ExecutionClient):
    """Context manager for executing code in an IPython kernel running in a `CodeExecutionContainer`.

    Provides stateful code execution within a container, maintaining kernel state between executions.
    Manages scoped skill and image storage directories.

    Args:
        key: Scope identifier used to:

            - Create scoped private skill directories for an executor instance
              (host path `{workspace.path}/skills/private/{key}`)
            - Create scoped image storage directories for an executor instance
              (host-only path `{workspace.path}/images/{key}`).
            - Set the working directory to the scoped private skill directory

        workspace: a `Workspace` instance defining the skill directory structure
        *args: Additional arguments passed to the `ExecutionClient` constructor
        **kwargs: Additional keyword arguments passed to the `ExecutionClient` constructor

    Example:
        ```python
        async with CodeExecutor(key="agent-1", workspace=container.workspace, port=container.port) as executor:
            # Execute code with access to skill directories
            await executor.execute("print('Hello')")
        ```
    """

    def __init__(self, key: str, workspace: Workspace, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.key = key
        self.workspace = workspace

        # Host mapping for working directory inside container
        self.working_dir = workspace.private_skills_path / key

        # images are stored on host only (for now)
        self.images_dir = workspace.path / "images" / key

    @property
    def skill_paths(self) -> List[Path]:
        """A path list containing the shared skill path and
        the scoped private skill path (= working directory).
        """
        return [self.workspace.shared_skills_path, self.working_dir]

    async def _init_kernel(self):
        """Initializes the IPython kernel environment.

        Creates necessary workspace directories and configures Python environment with:

        - Autoreload extension for development
        - Python path including shared and scoped private skill directories
        - Working directory set to scoped private skill directory

        Returns:
            Self reference for method chaining

        Note:
            This is called automatically when entering the context manager
        """
        await super()._init_kernel()

        await arun(self.working_dir.mkdir, parents=True, exist_ok=True)
        await arun(self.images_dir.mkdir, parents=True, exist_ok=True)

        await self.execute(f"""
            %load_ext autoreload
            %autoreload 2

            import os
            import sys

            workdir = "/home/appuser/skills/private/{self.key}"
            sys.path.extend(["/home/appuser/skills/shared", workdir])
            os.chdir(workdir)

            from freeact_skills.editor import file_editor
            """)
        return self
