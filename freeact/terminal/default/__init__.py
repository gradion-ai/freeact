from rich.console import Console

from freeact.agent import Agent
from freeact.permissions import PermissionManager
from freeact.terminal.default.app import FreeactApp
from freeact.terminal.default.config import DEFAULT_TERMINAL_UI_CONFIG, TerminalUiConfig


class Terminal:
    """Textual-based terminal interface for conversing with an agent.

    Drop-in replacement for the legacy Rich + prompt_toolkit terminal.
    """

    def __init__(
        self,
        agent: Agent,
        console: Console | None = None,
        ui_config: TerminalUiConfig = DEFAULT_TERMINAL_UI_CONFIG,
    ) -> None:
        """Initialize terminal with an agent.

        Args:
            agent: Agent instance to run conversations with.
            console: Accepted for interface compatibility but unused.
                Textual manages its own rendering.
            ui_config: Expand/collapse and keybinding settings for the Textual UI.
        """
        self._agent = agent
        self._main_agent_id = agent.agent_id
        self._permission_manager = PermissionManager()
        self._ui_config = ui_config

    async def run(self) -> None:
        """Run the interactive conversation loop until the user quits."""
        await self._permission_manager.load()

        async with self._agent:
            app = FreeactApp(
                agent_stream=self._agent.stream,
                permission_manager=self._permission_manager,
                main_agent_id=self._main_agent_id,
                ui_config=self._ui_config,
            )
            await app.run_async()
