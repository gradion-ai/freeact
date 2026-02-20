import subprocess

from freeact.terminal.default.clipboard import ClipboardAdapter


def test_macos_copy_uses_pbcopy() -> None:
    calls: list[tuple[tuple[str, ...], str | None]] = []

    def run_command(
        command: tuple[str, ...], input_text: str | None, timeout: float
    ) -> subprocess.CompletedProcess[str] | None:
        del timeout
        calls.append((command, input_text))
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    adapter = ClipboardAdapter(system_name="Darwin", run_command=run_command)

    assert adapter.copy("hello")
    assert calls == [(("pbcopy",), "hello")]


def test_linux_wayland_copy_falls_back_to_xclip_when_wlcopy_unavailable() -> None:
    calls: list[tuple[str, ...]] = []

    def run_command(
        command: tuple[str, ...], input_text: str | None, timeout: float
    ) -> subprocess.CompletedProcess[str] | None:
        del timeout, input_text
        calls.append(command)
        match command:
            case ("wl-copy",):
                return None
            case ("xclip", "-selection", "clipboard"):
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")
            case _:
                return subprocess.CompletedProcess(args=command, returncode=1, stdout="", stderr="error")

    adapter = ClipboardAdapter(
        system_name="Linux",
        env={"WAYLAND_DISPLAY": "wayland-0"},
        run_command=run_command,
    )

    assert adapter.copy("hello")
    assert calls == [
        ("wl-copy",),
        ("xclip", "-selection", "clipboard"),
    ]


def test_linux_x11_prefers_xclip_before_wayland_backend() -> None:
    calls: list[tuple[str, ...]] = []

    def run_command(
        command: tuple[str, ...], input_text: str | None, timeout: float
    ) -> subprocess.CompletedProcess[str] | None:
        del timeout, input_text
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=1, stdout="", stderr="error")

    adapter = ClipboardAdapter(
        system_name="Linux",
        env={"XDG_SESSION_TYPE": "x11"},
        run_command=run_command,
    )

    assert not adapter.copy("hello")
    assert calls[0] == ("xclip", "-selection", "clipboard")


def test_windows_paste_falls_back_to_pwsh() -> None:
    calls: list[tuple[str, ...]] = []

    def run_command(
        command: tuple[str, ...], input_text: str | None, timeout: float
    ) -> subprocess.CompletedProcess[str] | None:
        del timeout, input_text
        calls.append(command)
        match command[0]:
            case "powershell":
                return subprocess.CompletedProcess(args=command, returncode=1, stdout="", stderr="error")
            case "pwsh":
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="from pwsh", stderr="")
            case _:
                return None

    adapter = ClipboardAdapter(system_name="Windows", run_command=run_command)

    assert adapter.paste() == "from pwsh"
    assert calls[0][0] == "powershell"
    assert calls[1][0] == "pwsh"


def test_paste_returns_none_when_all_backends_fail() -> None:
    def run_command(
        command: tuple[str, ...], input_text: str | None, timeout: float
    ) -> subprocess.CompletedProcess[str] | None:
        del command, input_text, timeout
        return None

    adapter = ClipboardAdapter(system_name="Darwin", run_command=run_command)

    assert adapter.paste() is None


def test_paste_preserves_empty_clipboard_string() -> None:
    def run_command(
        command: tuple[str, ...], input_text: str | None, timeout: float
    ) -> subprocess.CompletedProcess[str] | None:
        del command, input_text, timeout
        return subprocess.CompletedProcess(args=("pbpaste",), returncode=0, stdout="", stderr="")

    adapter = ClipboardAdapter(system_name="Darwin", run_command=run_command)

    assert adapter.paste() == ""
