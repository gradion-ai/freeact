import os
import platform
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, TypeAlias

ClipboardCommand: TypeAlias = tuple[str, ...]
RunClipboardCommand: TypeAlias = Callable[
    [ClipboardCommand, str | None, float],
    subprocess.CompletedProcess[str] | None,
]


class ClipboardAdapterProtocol(Protocol):
    """Interface for clipboard access used by the terminal UI."""

    def copy(self, text: str) -> bool:
        """Copy text to the OS clipboard."""

    def paste(self) -> str | None:
        """Read text from the OS clipboard."""


@dataclass(frozen=True)
class ClipboardBackend:
    """Command pair used to interact with one clipboard implementation."""

    copy_command: ClipboardCommand
    paste_command: ClipboardCommand


def _default_run_command(
    command: ClipboardCommand, input_text: str | None, timeout: float
) -> subprocess.CompletedProcess[str] | None:
    """Run a clipboard command and return process output when available."""
    try:
        return subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _is_wayland(env: Mapping[str, str]) -> bool:
    """Determine if Wayland should be preferred for Linux clipboard access."""
    if env.get("WAYLAND_DISPLAY"):
        return True
    return env.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def _linux_backends(env: Mapping[str, str]) -> tuple[ClipboardBackend, ...]:
    """Get Linux clipboard command candidates in preferred order."""
    wl_backend = ClipboardBackend(copy_command=("wl-copy",), paste_command=("wl-paste", "--no-newline"))
    xclip_backend = ClipboardBackend(
        copy_command=("xclip", "-selection", "clipboard"),
        paste_command=("xclip", "-selection", "clipboard", "-o"),
    )
    xsel_backend = ClipboardBackend(
        copy_command=("xsel", "--clipboard", "--input"),
        paste_command=("xsel", "--clipboard", "--output"),
    )
    if _is_wayland(env):
        return (wl_backend, xclip_backend, xsel_backend)
    return (xclip_backend, xsel_backend, wl_backend)


def _windows_backends() -> tuple[ClipboardBackend, ...]:
    """Get Windows clipboard command candidates in preferred order."""
    powershell_backend = ClipboardBackend(
        copy_command=(
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$input | Set-Clipboard",
        ),
        paste_command=(
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-Clipboard -Raw",
        ),
    )
    pwsh_backend = ClipboardBackend(
        copy_command=(
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$input | Set-Clipboard",
        ),
        paste_command=(
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-Clipboard -Raw",
        ),
    )
    return (powershell_backend, pwsh_backend)


def _candidate_backends(system_name: str, env: Mapping[str, str]) -> tuple[ClipboardBackend, ...]:
    """Resolve clipboard backends for the active platform."""
    match system_name:
        case "Darwin":
            return (ClipboardBackend(copy_command=("pbcopy",), paste_command=("pbpaste",)),)
        case "Linux":
            return _linux_backends(env)
        case "Windows":
            return _windows_backends()
        case _:
            return ()


class ClipboardAdapter(ClipboardAdapterProtocol):
    """OS clipboard adapter for Textual terminal UI."""

    def __init__(
        self,
        system_name: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = 0.75,
        run_command: RunClipboardCommand | None = None,
    ) -> None:
        self._system_name = system_name or platform.system()
        self._env = env or os.environ
        self._timeout = timeout
        self._run_command = run_command or _default_run_command
        self._backends = _candidate_backends(self._system_name, self._env)

    def copy(self, text: str) -> bool:
        for backend in self._backends:
            result = self._run_command(backend.copy_command, text, self._timeout)
            if result is not None and result.returncode == 0:
                return True
        return False

    def paste(self) -> str | None:
        for backend in self._backends:
            result = self._run_command(backend.paste_command, None, self._timeout)
            if result is not None and result.returncode == 0:
                return result.stdout
        return None
