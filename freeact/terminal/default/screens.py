from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Label


class FilePickerScreen(ModalScreen[Path | None]):
    """Modal file picker triggered by `@` in the prompt input."""

    DEFAULT_CSS = """
    FilePickerScreen {
        align: center middle;
    }
    FilePickerScreen #picker-container {
        width: 70%;
        height: 70%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    FilePickerScreen #picker-label {
        dock: top;
        padding: 0 0 1 0;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical

        with Vertical(id="picker-container"):
            yield Label("Select a file (Escape to cancel)", id="picker-label")
            yield DirectoryTree(".", id="picker-tree")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.dismiss(event.path)

    def action_cancel(self) -> None:
        self.dismiss(None)
