import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Mapping
from uuid import uuid4

from dotenv import find_dotenv
from dotenv.main import DotEnv
from ipybox import Execution, ExecutionClient, ExecutionContainer, ExecutionError, ResourceClient, arun
from PIL import Image


class Workspace:
    """A workspace for private and shared agent skills i.e. Python modules that
    implement special agent skills. These are skills that are not pre-installed
    in the code execution container.

    A workspace defines paths for private and shared skills, both in the container
    and on the host machine. Workspace paths on the host machine can be bind-mounted
    into the container, if desired. This is especially useful when skills are being
    (inter)actively developed, so that they can be inspected and edited on the host
    machine while being executed in the container.

    Args:
        path: Root path of the workspace directory on the host.
        key: A key to designate:

            - a private skill sub-directory on the host
            - a private image sub-directory on the host
    """

    def __init__(self, path: Path | str | None = None, key: str | None = None):
        self._path = Path(path) if path else Path("workspace")
        self._key = key or "default"

    @property
    def skills_host_path(self) -> Path:
        """Path to skills root directory on host."""
        return self._path / "skills"

    @property
    def private_skills_host_path(self) -> Path:
        """Path to private skills directory on host."""
        return self.skills_host_path / "private" / self._key

    @property
    def shared_skills_host_path(self) -> Path:
        """Path to shared skills directory on host."""
        return self.skills_host_path / "shared"

    @property
    def private_images_host_path(self) -> Path:
        """Path to private images directory on host."""
        return self._path / "images" / self._key

    @property
    def private_skills_container_path(self) -> str:
        """Path to private skills directory in container."""
        return "skills/private/"

    @property
    def shared_skills_container_path(self) -> str:
        """Path to shared skills directory in container."""
        return "skills/shared"

    @property
    def private_mcp_container_path(self) -> str:
        """Path to private MCP directory in container."""
        return "skills/private/mcpgen"


class CodeExecutionContainer(ExecutionContainer):
    """Context manager for managing a code execution container's lifecycle.

    Extends [ipybox](https://gradion-ai.github.io/ipybox/)'s `ExecutionContainer`
    with [workspace][freeact.environment.Workspace]-specific bind mounts of skill directories.

    Args:
        tag: Name and optionally tag of the `ipybox` Docker image to use (format: `name:tag`)
        env: Environment variables to set in the container
        executor_port: Host port for the container's executor port. A random port is allocated if not specified.
        resource_port: Host port for the container's resource port. A random port is allocated if not specified.
        show_pull_progress: Whether to show progress when pulling the Docker image.
        workspace_path: Path to workspace directory on host. Defaults to "workspace".
        workspace_key: Key to designate private sub-directories on host. Defaults to "default".
    """

    def __init__(
        self,
        tag: str,
        env: dict[str, str] | None = None,
        executor_port: int | None = None,
        resource_port: int | None = None,
        show_pull_progress: bool = True,
        workspace_path: Path | str | None = None,
        workspace_key: str | None = None,
    ):
        self._workspace = Workspace(workspace_path, workspace_key)

        binds = {
            self._workspace.private_skills_host_path: self._workspace.private_skills_container_path,
            self._workspace.shared_skills_host_path: self._workspace.shared_skills_container_path,
        }

        env = (env or {}) | {
            "PYTHONPATH": f".:/app/{self._workspace.shared_skills_container_path}:/app/{self._workspace.private_skills_container_path}",
        }

        super().__init__(
            binds=binds,
            tag=tag,
            env=env,
            executor_port=executor_port,
            resource_port=resource_port,
            show_pull_progress=show_pull_progress,
        )

    @property
    def workspace(self) -> Workspace:
        """The container's workspace."""
        return self._workspace


@dataclass
class CodeExecutionResult:
    """Result of a [code execution][freeact.environment.CodeExecution]
    in a [code executor][freeact.environment.CodeExecutor].
    """

    text: str
    """Execution output text or error trace."""

    images: Dict[Path, Image.Image]
    """Images generated during code execution. Keys are image file paths in the
    [`container.workspace`][freeact.environment.CodeExecutionContainer.workspace],
    values are pre-loaded images from these files.
    """

    is_error: bool
    """Whether the execution resulted in an error. If `True`, `text` contains
    the corresponding error trace.
    """


class CodeExecution:
    """A code execution running in a [code executor][freeact.environment.CodeExecutor]."""

    def __init__(self, execution: Execution, images_dir: Path):
        self.execution = execution
        self.images_dir = images_dir
        self._result: CodeExecutionResult | None = None

    async def result(self, timeout: float = 120) -> CodeExecutionResult:
        """Retrieve the complete result of this code execution. Waits until the
        result is available.

        Args:
            timeout: Maximum time in seconds to wait for the execution result

        Raises:
            TimeoutError: If code execution duration exceeds the specified timeout
        """
        if self._result is None:
            async for _ in self.stream(timeout=timeout):
                pass
        return self._result  # type: ignore

    async def stream(self, timeout: float = 120) -> AsyncIterator[str]:
        """Stream the code execution result as it is generated. Once the stream
        is consumed, a [`result`][freeact.environment.CodeExecution.result] is
        immediately available without waiting.

        Generated images are not streamed. They can be obtained from the
        return value of [`result`][freeact.environment.CodeExecution.result].

        Args:
            timeout: Maximum time in seconds to wait for the execution result

        Raises:
            TimeoutError: If code execution duration exceeds the specified timeout
        """
        images = {}

        try:
            async for chunk in self.execution.stream(timeout=timeout):
                yield chunk
        except ExecutionError as e:
            is_error = True
            text = e.trace
            yield text
        except asyncio.TimeoutError:
            is_error = True
            text = "Execution timed out"
            yield text
        else:
            result = await self.execution.result()
            text = result.text
            is_error = False

            if result.images:
                chunk = "\n\nProduced images:"
                yield chunk
                text += chunk

            for i, image in enumerate(result.images):
                path = await self._save_image(image)
                chunk = f"\n![image_{i}]({path})"
                yield chunk
                text += chunk
                images[path] = image

        self._result = CodeExecutionResult(text=text, images=images, is_error=is_error)

    async def _save_image(self, image):
        image_id = uuid4().hex[:8]
        image_path = self.images_dir / f"{image_id}.png"
        await arun(image.save, str(image_path))
        return image_path


class CodeExecutor:
    """Context manager for executing code in an IPython kernel running in a
    [`CodeExecutionContainer`][freeact.environment.CodeExecutionContainer].
    The kernel is created on entering the context and destroyed on exit.

    Code execution is stateful for a given `CodeExecutor` instance. Definitions and
    variables of previous executions are available to subsequent executions.

    Args:
        workspace: The workspace of the code execution container
        port: Host port for the container's executor port
        host: Hostname or IP address of the container
    """

    def __init__(self, workspace: Workspace, port: int, host: str = "localhost"):
        self.workspace = workspace
        self.workspace.private_images_host_path.mkdir(parents=True, exist_ok=True)

        self._client = ExecutionClient(port=port, host=host)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def connect(self):
        await self._client.connect()
        await self._init_kernel()

    async def disconnect(self):
        await self._client.disconnect()

    async def execute(self, code: str, timeout: float = 120) -> CodeExecutionResult:
        """Executes code in this executor's IPython kernel and returns the result.

        Args:
            code: Code to execute
            timeout: Maximum time in seconds to wait for the execution result

        Raises:
            TimeoutError: If code execution duration exceeds the specified timeout
        """
        code_exec = await self.submit(code)
        return await code_exec.result(timeout=timeout)

    async def submit(self, code: str) -> CodeExecution:
        """Submits code for execution in this executor's IPython kernel and returns
        a [`CodeExecution`][freeact.environment.CodeExecution] object for consuming the
        execution result.

        Args:
            code: Python code to execute

        Returns:
            An [`CodeExecution`][freeact.environment.CodeExecution] object to track the code execution
        """
        code_exec = await self._client.submit(code)
        return CodeExecution(code_exec, self.workspace.private_images_host_path)

    async def _init_kernel(self):
        await self._client.execute(f"""
            %load_ext autoreload
            %autoreload 2

            import os
            import sys

            workdir = "/app/{self.workspace.private_skills_container_path}"
            os.chdir(workdir)

            from freeact_skills.editor import file_editor
            """)


class CodeProvider:
    """Context manager for

    - loading the source code of Python modules and generated MCP client functions
      from a [`CodeExecutionContainer`][freeact.environment.CodeExecutionContainer].
    - registering MCP servers and generating client functions for their tools in a
      [`CodeExecutionContainer`][freeact.environment.CodeExecutionContainer].

    Source code loaded with this context manager is provided as skill sources
    to code action models so that they can include them into code actions.

    Args:
        workspace: The workspace of the code execution container
        port: Host port for the container's resource port
        host: Hostname or IP address of the container
    """

    def __init__(self, workspace: Workspace, port: int, host: str = "localhost"):
        self.workspace = workspace
        self._client = ResourceClient(port, host)

    async def __aenter__(self):
        await self._client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.disconnect()

    async def register_mcp_servers(self, server_params_dict: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
        """Registers MCP servers and generates Python client functions for their tools. These
        functions can be included into code actions, and calling them runs the corresponding
        MCP server tools. This works for both `stdio` and `sse` based MCP servers.

        The source code of generated client functions can be loaded with the
        [`get_sources`][freeact.environment.CodeProvider.get_sources] method.

        Args:
            server_params_dict: Dictionary of application-defined server names and their MCP
                server parameters. `stdio` server parameters must specify at least a `command`
                key, `sse` server parameters must specify a `url` key. Application-defined
                server names must be valid Python module names.

        Returns:
            Dictionary of server names and provided tool names. Tool names are sanitized
            to be valid Python module names.
        """
        result = {}
        for server_name, server_params in server_params_dict.items():
            tool_names = await self._client.generate_mcp_sources(
                self.workspace.private_mcp_container_path, server_name, server_params
            )
            result[server_name] = tool_names
        return result

    async def get_sources(
        self,
        module_names: list[str] | None = None,
        mcp_tool_names: Mapping[str, list[str] | None] | None = None,
    ) -> str:
        """
        Loads the source code of given Python modules and generated MCP client functions
        and returns them in the following format:

            ```python
            # Module: {module_name_1}
            {module_source_1}
            ```

            ```python
            # Module: {module_name_2}
            {module_source_2}
            ```

            ...

        Module names of generated MCP client functions follow the pattern
        `mcpgen.{server_name}.{tool_name}`. Hence, calling

        ```python
        await get_sources(mcp_tool_names={"my_server": ["my_tool"]})
        ```

        is equivalent to

        ```python
        await get_sources(module_names=["mcpgen.my_server.my_tool"])
        ```

        For loading the source code of all generated client functions for an MCP server,
        use `None` as value in the `mcp_tool_names` dictionary:

        ```python
        await get_sources(mcp_tool_names={"my_server": None})
        ```

        Args:
            module_names: Names of modules available on the container's Python path
            mcp_tool_names: Dictionary of MCP server names and their tool names (as returned by
                [`register_mcp_servers`][freeact.environment.CodeProvider.register_mcp_servers]).
                Values can be `None` which means all tool names for a given server name.

        Returns:
            The formatted source code of all requested Python modules and generated MCP client functions.
        """
        mod_sources = await self._get_module_sources(module_names or [])
        mcp_sources = await self._get_mcp_sources(mcp_tool_names or {})
        return self._render(mod_sources | mcp_sources)

    async def _get_module_sources(self, module_names: list[str] | None = None) -> dict[str, str]:
        sources: dict[str, str] = {}
        for module_name in module_names or []:
            sources |= await self._client.get_module_sources(module_name)
        return sources

    async def _get_mcp_sources(self, mcp_tool_names: Mapping[str, list[str] | None]) -> dict[str, str]:
        sources: dict[str, str] = {}
        for server_name, tool_names in (mcp_tool_names or {}).items():
            tool_sources = await self._client.get_mcp_sources(self.workspace.private_mcp_container_path, server_name)
            tool_names = list(tool_sources.keys()) if tool_names is None else tool_names
            for tool_name in tool_names:
                if tool_name not in tool_sources:
                    raise ValueError(f"MCP tool {tool_name} not found for server {server_name}")
                sources[f"mcpgen.{server_name}.{tool_name}"] = tool_sources[tool_name]
        return sources

    def _render(self, sources: dict[str, str]) -> str:
        module_info_strings = []
        for module_name, module_source in sources.items():
            module_info_str = f"```python\n# Module: {module_name}\n\n{module_source}\n```"
            module_info_strings.append(module_info_str)
        return "\n\n".join(module_info_strings)


class CodeExecutionEnvironment:
    """An environment for

    - executing code actions in,
    - loading source code from,
    - and registering MCP servers at

    a running [`CodeExecutionContainer`][freeact.environment.CodeExecutionContainer].

    Args:
        container: A running code execution container.
    """

    def __init__(self, container: CodeExecutionContainer, host: str = "localhost"):
        self.container = container
        self.host = host

    @asynccontextmanager
    async def code_executor(self) -> AsyncIterator[CodeExecutor]:
        """Context manager for [`CodeExecutor`][freeact.environment.CodeExecutor]s in this environment."""
        async with CodeExecutor(
            workspace=self.container.workspace,
            port=self.container.executor_port,
            host=self.host,
        ) as executor:
            yield executor

    @asynccontextmanager
    async def code_provider(self) -> AsyncIterator[CodeProvider]:
        """Context manager for [`CodeProvider`][freeact.environment.CodeProvider]s in this environment."""
        async with CodeProvider(
            workspace=self.container.workspace,
            port=self.container.resource_port,
            host=self.host,
        ) as provider:
            yield provider


def dotenv_variables(dotenv_path: Path | None = Path(".env"), export: bool = True, **kwargs) -> Dict[str, str]:
    """Load environment variables from a `.env` file.

    Reads environment variables from a `.env` file and optionally exports them to `os.environ`.
    If no path is provided, searches for a `.env` file in parent directories.

    Args:
        dotenv_path: Path to the `.env` file. Defaults to `.env` in current directory.
        export: Whether to export variables to current environment. Defaults to `True`.
        **kwargs: Additional keyword arguments passed to `DotEnv` constructor.

    Returns:
        Dictionary mapping environment variable names to their values.
    """

    if dotenv_path is None:
        dotenv_path = find_dotenv()

    dotenv = DotEnv(dotenv_path=dotenv_path, **kwargs)

    if export:
        dotenv.set_as_environment_variables()

    return {k: v for k, v in dotenv.dict().items() if v is not None}


@asynccontextmanager
async def execution_environment(
    host: str = "localhost",
    ipybox_tag: str = "ghcr.io/gradion-ai/ipybox:minimal",
    ipybox_env: dict[str, str] = dotenv_variables(),
    executor_port: int | None = None,
    resource_port: int | None = None,
    workspace_path: Path | str | None = None,
    workspace_key: str | None = None,
) -> AsyncIterator[CodeExecutionEnvironment]:
    """Context manager providing a [`CodeExecutionEnvironment`][freeact.environment.CodeExecutionEnvironment]. It
    manages the lifecycle of the environment's [`CodeExecutionContainer`][freeact.environment.CodeExecutionContainer].

    Args:
        ipybox_tag: Name and optionally tag of the `ipybox` Docker image to use (format: `name:tag`)
        ipybox_env: Environment variables to set in the `ipybox` Docker container
        executor_port: Host port for the container's executor port. A random port is allocated if not specified
        resource_port: Host port for the container's resource port. A random port is allocated if not specified
        workspace_path: Path to workspace directory on host. Defaults to "workspace".
        workspace_key: Key to designate private sub-directories on host. Defaults to "default".
    """
    async with CodeExecutionContainer(
        tag=ipybox_tag,
        env=ipybox_env,
        executor_port=executor_port,
        resource_port=resource_port,
        workspace_path=workspace_path,
        workspace_key=workspace_key,
    ) as container:
        yield CodeExecutionEnvironment(container=container, host=host)
