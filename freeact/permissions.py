import json
from pathlib import Path
from typing import Any

import aiofiles


class PermissionManager:
    """Tool permission gating with two-tier approval: always-allowed (persisted)
    and session-only (in-memory).

    Filesystem tools targeting paths within `.freeact/` are auto-approved
    without explicit permission grants.
    """

    def __init__(self, freeact_dir: Path = Path(".freeact")):
        self._freeact_dir = freeact_dir.resolve()
        self._permissions_file = self._freeact_dir / "permissions.json"
        self._filesystem_tools = frozenset(
            {
                "filesystem_read_file",
                "filesystem_read_text_file",
                "filesystem_write_file",
                "filesystem_edit_file",
                "filesystem_create_directory",
                "filesystem_list_directory",
                "filesystem_directory_tree",
                "filesystem_search_files",
                "filesystem_read_multiple_files",
            }
        )
        self._allowed_always: set[str] = set()
        self._allowed_session: set[str] = set()
        self._freeact_dir.mkdir(parents=True, exist_ok=True)

    async def load(self) -> None:
        """Load always-allowed tools from `.freeact/permissions.json`."""
        if self._permissions_file.exists():
            async with aiofiles.open(self._permissions_file) as f:
                text = await f.read()
            data = json.loads(text)
            self._allowed_always = set(data.get("allowed_tools", []))

    async def save(self) -> None:
        """Persist always-allowed tools to `.freeact/permissions.json`."""
        data = {"allowed_tools": sorted(self._allowed_always)}
        content = json.dumps(data, indent=2)
        async with aiofiles.open(self._permissions_file, "w") as f:
            await f.write(content)

    def is_allowed(self, tool_name: str, tool_args: dict[str, Any] | None = None) -> bool:
        """Check if a tool call is pre-approved.

        Returns `True` if the tool is in the always-allowed or session-allowed
        set, or if it's a filesystem tool operating within `.freeact/`.
        """
        if tool_name in self._allowed_always or tool_name in self._allowed_session:
            return True

        if tool_name in self._filesystem_tools and tool_args:
            match tool_args:
                case {"paths": paths}:
                    return all(self._is_within_freeact(p) for p in paths)
                case {"path": path}:
                    return self._is_within_freeact(path)

        return False

    def _is_within_freeact(self, path_str: str) -> bool:
        path = Path(path_str).resolve()
        return path == self._freeact_dir or self._freeact_dir in path.parents

    async def allow_always(self, tool_name: str) -> None:
        """Grant permanent permission for a tool and persist to disk."""
        self._allowed_always.add(tool_name)
        await self.save()

    def allow_session(self, tool_name: str) -> None:
        """Grant permission for a tool until the session ends (not persisted)."""
        self._allowed_session.add(tool_name)
