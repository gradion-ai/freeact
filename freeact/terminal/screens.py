from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.reactive import var
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Label, OptionList
from textual.widgets.option_list import Option

from freeact.agent.config.skills import SkillMetadata
from freeact.terminal.prefix_match import find_prefix_match


def _filesystem_root(path: Path) -> Path:
    """Resolve and return the filesystem root for `path`.

    Args:
        path: Path used to determine the filesystem root.

    Returns:
        Root path (for example `/` on POSIX systems).
    """
    resolved = path.resolve()
    if resolved.anchor:
        return Path(resolved.anchor)
    return resolved


class FilePickerTree(DirectoryTree):
    """Directory tree with explicit keybindings for picker navigation."""

    auto_expand = var(False)

    BINDINGS = [
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("left", "collapse_cursor_node", "Collapse"),
        ("right", "expand_cursor_node", "Expand"),
        ("enter", "select_cursor", "Select"),
    ]

    def action_expand_cursor_node(self) -> None:
        """Expand the directory under the cursor when possible."""
        cursor_node = self.cursor_node
        if cursor_node is None:
            return
        dir_entry = cursor_node.data
        if dir_entry is None:
            return
        if self._safe_is_dir(dir_entry.path):
            cursor_node.expand()

    def action_collapse_cursor_node(self) -> None:
        """Collapse the directory under the cursor when possible."""
        cursor_node = self.cursor_node
        if cursor_node is None:
            return
        dir_entry = cursor_node.data
        if dir_entry is None:
            return
        if self._safe_is_dir(dir_entry.path):
            cursor_node.collapse()


class FilePickerScreen(ModalScreen[Path | None]):
    """Modal file picker opened from `@path` prompt completion."""

    _BASE_LABEL = "Select a file or directory (Enter to select, Escape to cancel)"

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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._prefix = ""

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical

        with Vertical(id="picker-container"):
            yield Label(self._BASE_LABEL, id="picker-label")
            yield FilePickerTree(_filesystem_root(Path.cwd()), id="picker-tree")

    async def on_mount(self) -> None:
        tree = self.query_one("#picker-tree", FilePickerTree)
        tree.focus()
        await self._focus_tree_path(tree, Path.cwd())

    def _on_key(self, event: "textual.events.Key") -> None:  # type: ignore[name-defined]  # noqa: F821
        if event.key in ("up", "down", "left", "right"):
            self._prefix = ""
            self._update_label()
            return

        if event.is_printable and event.character:
            event.stop()
            event.prevent_default()
            self._prefix += event.character
            self._apply_prefix_match()
        elif event.key == "backspace":
            event.stop()
            event.prevent_default()
            self._prefix = self._prefix[:-1]
            self._apply_prefix_match()

    def _apply_prefix_match(self) -> None:
        if not self._prefix:
            self._update_label()
            return

        tree = self.query_one("#picker-tree", FilePickerTree)
        cursor = tree.cursor_node
        if cursor is None:
            self._update_label()
            return

        if cursor.is_expanded and cursor.children:
            allowed = set(id(c) for c in cursor.children)
        else:
            parent = cursor.parent or tree.root
            allowed = set(id(c) for c in parent.children)

        labels: list[str] = []
        nodes: list[Any] = []
        for line in range(tree.last_line + 1):
            node = tree.get_node_at_line(line)
            if node is not None and id(node) in allowed:
                labels.append(str(node.label))
                nodes.append(node)

        result = find_prefix_match(labels, self._prefix)
        if result is not None:
            index, effective = result
            self._prefix = effective
            tree.move_cursor(nodes[index])

        self._update_label()

    def _update_label(self) -> None:
        label = self.query_one("#picker-label", Label)
        if self._prefix:
            label.update(f"{self._BASE_LABEL}  filter: {self._prefix}")
        else:
            label.update(self._BASE_LABEL)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.dismiss(event.path)

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.dismiss(event.path)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @staticmethod
    def _find_child(node: Any, path: Path) -> Any | None:
        """Find a direct child tree node for a filesystem path.

        Args:
            node: Parent tree node to search under.
            path: Target filesystem path to match.

        Returns:
            Matching child node, or `None` when no child matches.
        """
        for child in node.children:
            data = child.data
            if data is not None and data.path == path:
                return child
        return None

    async def _focus_tree_path(self, tree: FilePickerTree, target_path: Path) -> None:
        """Move the picker cursor to the closest node for `target_path`.

        Args:
            tree: Picker tree widget to navigate.
            target_path: Filesystem path to focus when reachable from the tree root.
        """
        node = tree.root
        root_path = Path(tree.path).resolve()
        target_resolved = target_path.resolve()
        await tree.reload_node(node)
        if root_path == target_resolved:
            tree.move_cursor(node, animate=False)
            return

        try:
            relative_parts = target_resolved.relative_to(root_path).parts
        except ValueError:
            tree.move_cursor(node, animate=False)
            return

        current_path = root_path
        for part in relative_parts:
            next_path = current_path / part
            child = self._find_child(node, next_path)
            if child is None:
                break
            node = child
            current_path = next_path
            if child.allow_expand:
                await tree.reload_node(child)
        tree.move_cursor(node, animate=False)


class SkillPickerScreen(ModalScreen[str | None]):
    """Modal skill picker opened from `/` prompt completion."""

    DEFAULT_CSS = """
    SkillPickerScreen {
        align: center middle;
    }
    SkillPickerScreen #skill-picker-container {
        width: 70%;
        height: 50%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    SkillPickerScreen #skill-picker-label {
        dock: top;
        padding: 0 0 1 0;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    _BASE_LABEL = "Select a skill (Enter to select, Escape to cancel)"

    def __init__(self, skills: list[SkillMetadata]) -> None:
        super().__init__()
        self._skills = skills
        self._prefix = ""

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical

        with Vertical(id="skill-picker-container"):
            yield Label(self._BASE_LABEL, id="skill-picker-label")
            option_list = OptionList(
                *[Option(s.name, id=s.name) for s in self._skills],
                id="skill-picker-list",
            )
            yield option_list

    def on_mount(self) -> None:
        self.query_one("#skill-picker-list", OptionList).focus()

    def _on_key(self, event: "textual.events.Key") -> None:  # type: ignore[name-defined]  # noqa: F821
        if event.is_printable and event.character:
            event.stop()
            event.prevent_default()
            self._prefix += event.character
            self._apply_prefix_match()
        elif event.key == "backspace":
            event.stop()
            event.prevent_default()
            self._prefix = self._prefix[:-1]
            self._apply_prefix_match()

    def _apply_prefix_match(self) -> None:
        label = self.query_one("#skill-picker-label", Label)
        if not self._prefix:
            label.update(self._BASE_LABEL)
            return

        names = [s.name for s in self._skills]
        result = find_prefix_match(names, self._prefix)
        if result is not None:
            index, effective = result
            self._prefix = effective
            option_list = self.query_one("#skill-picker-list", OptionList)
            option_list.highlighted = index
            option_list.scroll_to_highlight()

        label.update(f"{self._BASE_LABEL}  filter: {self._prefix}")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)
