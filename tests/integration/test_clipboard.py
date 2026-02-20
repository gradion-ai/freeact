import os
import platform
import secrets
import shutil

import pytest

from freeact.terminal.default.clipboard import ClipboardAdapter


def _random_payload() -> str:
    """Generate a unique clipboard payload for round-trip assertions."""
    return f"freeact-clipboard-{secrets.token_hex(8)}"


def _skip_if_missing_commands(*commands: str) -> None:
    """Skip when any required command is unavailable on PATH."""
    missing = [command for command in commands if shutil.which(command) is None]
    if missing:
        pytest.skip(f"Missing clipboard command(s): {', '.join(missing)}")


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-only integration test")
def test_clipboard_adapter_roundtrip_on_macos() -> None:
    _skip_if_missing_commands("pbcopy", "pbpaste")
    adapter = ClipboardAdapter()
    original = adapter.paste()
    payload = _random_payload()

    try:
        if not adapter.copy(payload):
            pytest.skip("pbcopy unavailable in current runtime environment")
        pasted = adapter.paste()
        if pasted is None:
            pytest.skip("pbpaste unavailable in current runtime environment")
        assert pasted == payload
    finally:
        if original is not None:
            adapter.copy(original)


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only integration test")
def test_clipboard_adapter_roundtrip_on_linux() -> None:
    has_wayland_pair = shutil.which("wl-copy") is not None and shutil.which("wl-paste") is not None
    has_xclip = shutil.which("xclip") is not None
    has_xsel = shutil.which("xsel") is not None
    if not (has_wayland_pair or has_xclip or has_xsel):
        pytest.skip("No Linux clipboard backend commands available")

    adapter = ClipboardAdapter(env=os.environ)
    original = adapter.paste()
    payload = _random_payload()

    try:
        if not adapter.copy(payload):
            pytest.skip("Linux clipboard backend unavailable in current runtime environment")
        pasted = adapter.paste()
        if pasted is None:
            pytest.skip("Linux clipboard paste unavailable in current runtime environment")
        assert pasted == payload
    finally:
        if original is not None:
            adapter.copy(original)


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only integration test")
def test_clipboard_adapter_roundtrip_on_windows() -> None:
    if shutil.which("powershell") is None and shutil.which("pwsh") is None:
        pytest.skip("No PowerShell executable available for clipboard integration")

    adapter = ClipboardAdapter()
    original = adapter.paste()
    payload = _random_payload()

    try:
        if not adapter.copy(payload):
            pytest.skip("Windows clipboard backend unavailable in current runtime environment")
        pasted = adapter.paste()
        if pasted is None:
            pytest.skip("Windows clipboard paste unavailable in current runtime environment")
        assert pasted == payload
    finally:
        if original is not None:
            adapter.copy(original)
