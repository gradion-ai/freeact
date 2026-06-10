# Covers behavior-inventory.md sections: 20 (terminal UI: clipboard backends, platform roundtrips)
import os
import platform
import secrets
import shutil

import pytest

from freeact.terminal.clipboard import ClipboardAdapter


def _assert_roundtrip(adapter: ClipboardAdapter) -> None:
    """Copy a unique payload, paste it back and restore the original clipboard."""
    original = adapter.paste()
    payload = f"freeact-clipboard-{secrets.token_hex(8)}"

    try:
        if not adapter.copy(payload):
            pytest.skip("Clipboard copy unavailable in current runtime environment")
        pasted = adapter.paste()
        if pasted is None:
            pytest.skip("Clipboard paste unavailable in current runtime environment")
        assert pasted == payload
    finally:
        if original is not None:
            adapter.copy(original)


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-only integration test")
def test_clipboard_adapter_roundtrip_on_macos() -> None:
    missing = [command for command in ("pbcopy", "pbpaste") if shutil.which(command) is None]
    if missing:
        pytest.skip(f"Missing clipboard command(s): {', '.join(missing)}")
    _assert_roundtrip(ClipboardAdapter())


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only integration test")
def test_clipboard_adapter_roundtrip_on_linux() -> None:
    has_wayland_pair = shutil.which("wl-copy") is not None and shutil.which("wl-paste") is not None
    has_xclip = shutil.which("xclip") is not None
    has_xsel = shutil.which("xsel") is not None
    if not (has_wayland_pair or has_xclip or has_xsel):
        pytest.skip("No Linux clipboard backend commands available")
    _assert_roundtrip(ClipboardAdapter(env=os.environ))


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only integration test")
def test_clipboard_adapter_roundtrip_on_windows() -> None:
    if shutil.which("powershell") is None and shutil.which("pwsh") is None:
        pytest.skip("No PowerShell executable available for clipboard integration")
    _assert_roundtrip(ClipboardAdapter())
