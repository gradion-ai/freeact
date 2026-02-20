from rich.console import Console

from freeact.agent import Agent
from freeact.permissions import PermissionManager
from freeact.terminal.default.app import FreeactApp
from freeact.terminal.default.config import DEFAULT_TERMINAL_UI_CONFIG, TerminalUiConfig


class Terminal:
    """Textual terminal interface for interactive agent conversations.

    This class replaces the legacy Rich + prompt_toolkit interface while
    preserving the same high-level terminal contract.
    """

    def __init__(
        self,
        agent: Agent,
        console: Console | None = None,
        ui_config: TerminalUiConfig = DEFAULT_TERMINAL_UI_CONFIG,
    ) -> None:
        """Initialize a terminal session wrapper around an agent.

        Args:
            agent: Agent instance used to execute conversation turns.
            console: Compatibility parameter for legacy interfaces. Textual
                manages rendering directly, so this value is ignored.
            ui_config: Keybinding and expand/collapse behavior for the UI.
        """
        self._agent = agent
        self._main_agent_id = agent.agent_id
        self._permission_manager = PermissionManager()
        self._ui_config = ui_config

    async def run(self) -> None:
        """Run the interactive terminal UI until the user exits."""
        await self._permission_manager.load()

        async with self._agent:
            app = FreeactApp(
                agent_stream=self._agent.stream,
                permission_manager=self._permission_manager,
                main_agent_id=self._main_agent_id,
                ui_config=self._ui_config,
            )
            await app.run_async()
