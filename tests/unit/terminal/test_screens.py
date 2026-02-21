from pathlib import Path

import pytest
from textual.binding import Binding

from freeact.terminal.screens import FilePickerScreen, FilePickerTree


def _binding_to_pair(binding: Binding | tuple[str, str, str]) -> tuple[str, str]:
    match binding:
        case Binding():
            return binding.key, binding.action
        case _:
            return binding[0], binding[1]


def test_file_picker_tree_key_bindings() -> None:
    keymap = dict(_binding_to_pair(binding) for binding in FilePickerTree.BINDINGS)

    assert keymap["up"] == "cursor_up"
    assert keymap["down"] == "cursor_down"
    assert keymap["left"] == "collapse_cursor_node"
    assert keymap["right"] == "expand_cursor_node"
    assert keymap["enter"] == "select_cursor"


def test_file_picker_tree_auto_expand_disabled() -> None:
    assert not FilePickerTree.auto_expand._default


def test_file_picker_screen_dismisses_on_directory_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    selected: Path | None = None
    screen = FilePickerScreen()
    path = Path("/tmp/example")

    def fake_dismiss(result: Path | None) -> None:
        nonlocal selected
        selected = result

    monkeypatch.setattr(screen, "dismiss", fake_dismiss)
    event = DirectorySelectedEvent(path=path)

    screen.on_directory_tree_directory_selected(event)  # type: ignore[arg-type]

    assert selected == path


class DirectorySelectedEvent:
    """Minimal event stub with a selected path."""

    def __init__(self, path: Path) -> None:
        self.path = path
