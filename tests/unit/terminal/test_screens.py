from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Label

from freeact.agent.config.skills import SkillMetadata
from freeact.terminal.screens import FilePickerScreen, FilePickerTree, SkillPickerScreen


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


# --- Helpers for Textual screen tests ---


def _make_skill(name: str, tmp_path: Path, description: str = "A skill") -> SkillMetadata:
    skill_dir = tmp_path / name
    skill_dir.mkdir(exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(f"---\nname: {name}\ndescription: {description}\n---\n# {name}")
    return SkillMetadata(name=name, description=description, path=skill_file)


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


# --- Skill picker prefix matching tests ---


@pytest.mark.asyncio
async def test_skill_picker_char_highlights_first_match(tmp_path: Path) -> None:
    skills = [_make_skill(n, tmp_path) for n in ["aab", "abc", "bcd"]]
    app = _SkillPickerApp(skills)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.pause(0.05)

        picker = next(s for s in app.screen_stack if isinstance(s, SkillPickerScreen))
        option_list = picker.query_one("#skill-picker-list")
        assert option_list.highlighted == 0


@pytest.mark.asyncio
async def test_skill_picker_two_char_prefix(tmp_path: Path) -> None:
    skills = [_make_skill(n, tmp_path) for n in ["aab", "abc", "bcd"]]
    app = _SkillPickerApp(skills)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.press("b")
        await pilot.pause(0.05)

        picker = next(s for s in app.screen_stack if isinstance(s, SkillPickerScreen))
        option_list = picker.query_one("#skill-picker-list")
        assert option_list.highlighted == 1


@pytest.mark.asyncio
async def test_skill_picker_no_better_match_keeps_selection(tmp_path: Path) -> None:
    skills = [_make_skill(n, tmp_path) for n in ["aab", "abc", "bcd"]]
    app = _SkillPickerApp(skills)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.press("b")
        await pilot.press("b")
        await pilot.pause(0.05)

        picker = next(s for s in app.screen_stack if isinstance(s, SkillPickerScreen))
        option_list = picker.query_one("#skill-picker-list")
        assert option_list.highlighted == 1


@pytest.mark.asyncio
async def test_skill_picker_backspace(tmp_path: Path) -> None:
    skills = [_make_skill(n, tmp_path) for n in ["aab", "abc", "bcd"]]
    app = _SkillPickerApp(skills)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.press("b")
        await pilot.pause(0.05)

        picker = next(s for s in app.screen_stack if isinstance(s, SkillPickerScreen))
        option_list = picker.query_one("#skill-picker-list")
        assert option_list.highlighted == 1

        await pilot.press("backspace")
        await pilot.pause(0.05)
        assert option_list.highlighted == 0


@pytest.mark.asyncio
async def test_skill_picker_enter_selects_highlighted(tmp_path: Path) -> None:
    skills = [_make_skill(n, tmp_path) for n in ["aab", "abc", "bcd"]]
    app = _SkillPickerApp(skills)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await pilot.press("b")
        await pilot.pause(0.05)
        await pilot.press("enter")
        await pilot.pause(0.05)

        assert app._picker_result == "bcd"


# --- File picker prefix matching tests ---


class _FilePickerApp(App[Path | None]):
    """Minimal app that immediately pushes a FilePickerScreen."""

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(FilePickerScreen(), callback=self._on_result)

    def _on_result(self, result: Path | None) -> None:
        self._picker_result = result


@pytest.mark.asyncio
async def test_file_picker_char_navigates_to_matching_node(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "alpha.txt").touch()
    (tmp_path / "beta.txt").touch()
    (tmp_path / "gamma.txt").touch()
    monkeypatch.chdir(tmp_path)

    app = _FilePickerApp()

    async with app.run_test() as pilot:
        await pilot.pause(0.5)

        picker = next(s for s in app.screen_stack if isinstance(s, FilePickerScreen))
        tree = picker.query_one("#picker-tree", FilePickerTree)

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
    # The cwd node "sub" has children "aaa.txt" and "bbb.txt".
    # Its parent (tmp_path) is also visible and named something like
    # "test_file_picker_expanded_...0" but more importantly the ancestor
    # chain always contains system dirs.  We create a child dir whose name
    # starts with a letter that also appears as a system-level ancestor
    # (e.g. "tmp" is an ancestor).  Typing "t" from the expanded cwd must
    # NOT jump to /tmp -- it should match "target.txt" inside cwd.
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "apple.txt").touch()
    (sub / "target.txt").touch()
    monkeypatch.chdir(sub)

    app = _FilePickerApp()

    async with app.run_test() as pilot:
        await pilot.pause(0.5)

        picker = next(s for s in app.screen_stack if isinstance(s, FilePickerScreen))
        tree = picker.query_one("#picker-tree", FilePickerTree)

        # Cursor starts on the expanded cwd ("sub")
        assert tree.cursor_node is not None
        assert "sub" in str(tree.cursor_node.label).lower()

        # Type "t" -- should match "target.txt" (child), not /tmp (ancestor)
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

        picker = next(s for s in app.screen_stack if isinstance(s, FilePickerScreen))
        tree = picker.query_one("#picker-tree", FilePickerTree)

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

        picker = next(s for s in app.screen_stack if isinstance(s, FilePickerScreen))
        tree = picker.query_one("#picker-tree", FilePickerTree)

        initial_line = tree.cursor_line
        await pilot.press("down")
        await pilot.pause(0.05)
        assert tree.cursor_line != initial_line
