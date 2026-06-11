# Covers behavior-inventory.md sections: 20 (terminal UI: file picker and skill picker screens)
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Label, OptionList

from freeact.config import SkillMetadata
from freeact.terminal.screens import FilePickerScreen, FilePickerTree, SkillPickerScreen
from tests.unit.terminal.conftest import find_screen, make_skill


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


class DirectorySelectedEvent:
    """Minimal event stub with a selected path."""

    def __init__(self, path: Path) -> None:
        self.path = path


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


class _SkillPickerApp(App[str | None]):
    """Minimal app that immediately pushes a SkillPickerScreen."""

    def __init__(self, skills: list[SkillMetadata]) -> None:
        super().__init__()
        self._skills = skills

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(SkillPickerScreen(self._skills), callback=self._on_result)

    def _on_result(self, result: str | None) -> None:
        self._picker_result = result


@pytest.fixture
def skill_picker_app() -> _SkillPickerApp:
    skills = [make_skill(n) for n in ["aab", "abc", "bcd"]]
    return _SkillPickerApp(skills)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("keys", "expected_highlighted"),
    [
        (["a"], 0),
        (["a", "b"], 1),
        (["a", "b", "b"], 1),
    ],
    ids=["single_char_first_match", "two_char_prefix", "no_better_match_keeps_selection"],
)
async def test_skill_picker_prefix_highlights_match(
    skill_picker_app: _SkillPickerApp, keys: list[str], expected_highlighted: int
) -> None:
    async with skill_picker_app.run_test() as pilot:
        await pilot.pause(0.05)
        await pilot.press(*keys)
        await pilot.pause(0.05)

        option_list = skill_picker_app.screen.query_one("#skill-picker-list", OptionList)
        assert option_list.highlighted == expected_highlighted


@pytest.mark.asyncio
async def test_skill_picker_backspace(skill_picker_app: _SkillPickerApp) -> None:
    async with skill_picker_app.run_test() as pilot:
        await pilot.pause(0.05)
        await pilot.press("a", "b")
        await pilot.pause(0.05)

        option_list = skill_picker_app.screen.query_one("#skill-picker-list", OptionList)
        assert option_list.highlighted == 1

        await pilot.press("backspace")
        await pilot.pause(0.05)
        assert option_list.highlighted == 0


@pytest.mark.asyncio
async def test_skill_picker_enter_selects_highlighted(skill_picker_app: _SkillPickerApp) -> None:
    app = skill_picker_app

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await pilot.press("b")
        await pilot.pause(0.05)
        await pilot.press("enter")
        await pilot.pause(0.05)

        assert app._picker_result == "bcd"


class _FilePickerApp(App[Path | None]):
    """Minimal app that immediately pushes a FilePickerScreen."""

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(FilePickerScreen(), callback=self._on_result)

    def _on_result(self, result: Path | None) -> None:
        self._picker_result = result


def _picker_tree(app: _FilePickerApp) -> FilePickerTree:
    return find_screen(app, FilePickerScreen).query_one("#picker-tree", FilePickerTree)


@pytest.mark.asyncio
async def test_file_picker_char_navigates_to_matching_node(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "alpha.txt").touch()
    (tmp_path / "beta.txt").touch()
    (tmp_path / "gamma.txt").touch()
    monkeypatch.chdir(tmp_path)

    app = _FilePickerApp()

    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        tree = _picker_tree(app)

        # Type "b" to match "beta.txt" among children of the expanded cwd node
        await pilot.press("b")
        await pilot.pause(0.1)

        cursor = tree.cursor_node
        assert cursor is not None
        assert "beta" in str(cursor.label).lower()


@pytest.mark.asyncio
async def test_file_picker_expanded_dir_searches_children_not_ancestors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When cursor is on an expanded directory, prefix search is scoped to its children.

    The tree has ancestor nodes visible above the cwd. Typing a prefix that
    matches an ancestor name must NOT jump to that ancestor -- it should only
    search among children of the expanded cwd node.
    """
    # The cwd node "sub" has children "apple.txt" and "target.txt". The
    # ancestor chain always contains system dirs (e.g. "tmp"). Typing "t"
    # from the expanded cwd must NOT jump to /tmp -- it should match
    # "target.txt" inside cwd.
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "apple.txt").touch()
    (sub / "target.txt").touch()
    monkeypatch.chdir(sub)

    app = _FilePickerApp()

    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        tree = _picker_tree(app)

        # Cursor starts on the expanded cwd ("sub")
        assert tree.cursor_node is not None
        assert "sub" in str(tree.cursor_node.label).lower()

        await pilot.press("t")
        await pilot.pause(0.1)

        cursor = tree.cursor_node
        assert cursor is not None
        assert "target" in str(cursor.label).lower()


@pytest.mark.asyncio
async def test_file_picker_file_cursor_searches_siblings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When cursor is on a file, prefix search is scoped to siblings."""
    (tmp_path / "alpha.txt").touch()
    (tmp_path / "beta.txt").touch()
    (tmp_path / "gamma.txt").touch()
    monkeypatch.chdir(tmp_path)

    app = _FilePickerApp()

    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        tree = _picker_tree(app)

        # Move cursor down to first child (a file node)
        await pilot.press("down")
        await pilot.pause(0.05)

        cursor_before = tree.cursor_node
        assert cursor_before is not None
        assert "alpha" in str(cursor_before.label).lower()

        # Type "g" -- should match "gamma.txt" (sibling), not any ancestor
        await pilot.press("g")
        await pilot.pause(0.1)

        cursor = tree.cursor_node
        assert cursor is not None
        assert "gamma" in str(cursor.label).lower()


@pytest.mark.asyncio
async def test_file_picker_arrow_keys_still_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "alpha.txt").touch()
    (tmp_path / "beta.txt").touch()
    monkeypatch.chdir(tmp_path)

    app = _FilePickerApp()

    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        tree = _picker_tree(app)

        initial_line = tree.cursor_line
        await pilot.press("down")
        await pilot.pause(0.05)
        assert tree.cursor_line != initial_line
