from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Collapsible, Static

_BANNER_PATH = Path(__file__).with_name("banner.txt")


class TrackedCollapsible(Collapsible):
    """Collapsible that distinguishes user toggles from programmatic changes.

    User-driven toggles (title click or `Enter` on the focused title) post a
    [`UserToggled`][freeact.terminal.view.TrackedCollapsible.UserToggled]
    message. Programmatic changes via `set_collapsed()` do not.
    """

    class UserToggled(Message):
        """Message emitted when the user toggles the collapsible."""

        def __init__(self, collapsible: "TrackedCollapsible", collapsed: bool) -> None:
            super().__init__()
            self.collapsible = collapsible
            self.collapsed = collapsed

        @property
        def control(self) -> "TrackedCollapsible":
            return self.collapsible

    _programmatic: bool = False

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the collapsed state programmatically (no user-toggle message)."""
        self._programmatic = True
        try:
            self.collapsed = collapsed
        finally:
            self._programmatic = False

    def watch_collapsed(self, collapsed: bool) -> None:
        # Textual's Collapsible renders via the private `_watch_collapsed`
        # watcher; this public watcher runs additionally and only observes.
        # The base class's title-toggle handler is the only path that changes
        # `collapsed` outside `set_collapsed()`, so any non-programmatic
        # change on a mounted widget is a user toggle. (Overriding
        # `_on_collapsible_title_toggle` instead would double-fire: Textual
        # dispatches that handler for every class in the MRO.)
        if self.is_mounted and not self._programmatic:
            self.post_message(self.UserToggled(self, collapsed))


@dataclass
class CollapsePolicy:
    """Collapse policy state shared across tracked `Collapsible` widgets.

    Resolution precedence: `expand_all_override` > manual toggle > forced
    expansion (pending-approval pin, active subagent task) > configured
    state. Manual beats forced so an active subagent task can be manually
    collapsed and stays collapsed as children mount.
    """

    schedule_scroll: Callable[[], None]
    expand_all_override: bool = False
    configured_collapsed: dict[int, bool] = field(default_factory=dict)
    manual_collapsed: dict[int, bool] = field(default_factory=dict)
    forced_expanded_ids: set[int] = field(default_factory=set)

    def register(self, box: TrackedCollapsible, configured_collapsed: bool, force_expanded: bool = False) -> None:
        """Start tracking a widget and apply its initial render state."""
        box_id = id(box)
        self.configured_collapsed[box_id] = configured_collapsed
        if force_expanded:
            self.forced_expanded_ids.add(box_id)
        else:
            self.forced_expanded_ids.discard(box_id)
        self.apply(box)

    def set_configured(self, box: TrackedCollapsible, collapsed: bool) -> None:
        """Update the configured collapsed state for a tracked widget."""
        self.configured_collapsed[id(box)] = collapsed
        self.apply(box)

    def set_forced(self, box: TrackedCollapsible, enabled: bool) -> None:
        """Enable or disable forced expansion for a tracked widget."""
        box_id = id(box)
        if enabled:
            self.forced_expanded_ids.add(box_id)
        else:
            self.forced_expanded_ids.discard(box_id)
        self.apply(box)

    def apply(self, box: TrackedCollapsible) -> None:
        """Resolve and apply the current collapsed state for a widget."""
        box_id = id(box)
        configured_collapsed = self.configured_collapsed.get(box_id, box.collapsed)
        manual_collapsed = self.manual_collapsed.get(box_id)
        if self.expand_all_override:
            collapsed = False
        elif manual_collapsed is not None:
            collapsed = manual_collapsed
        elif box_id in self.forced_expanded_ids:
            collapsed = False
        else:
            collapsed = configured_collapsed

        if box.collapsed == collapsed:
            return

        box.set_collapsed(collapsed)
        self.schedule_scroll()

    def toggle_expand_all(self, widgets: list[Widget]) -> None:
        """Flip the global expand-all override and reapply all tracked widgets."""
        self.expand_all_override = not self.expand_all_override
        for widget in widgets:
            match widget:
                case TrackedCollapsible() as box:
                    self.apply(box)

    def record_manual_toggle(self, box: TrackedCollapsible, collapsed: bool) -> None:
        """Persist a user-driven collapsed state for a tracked widget."""
        box_id = id(box)
        if box_id in self.configured_collapsed:
            self.manual_collapsed[box_id] = collapsed


def _load_banner() -> Text | None:
    """Load startup banner text from the bundled ANSI art file.

    Returns:
        Parsed Rich `Text` banner, or `None` when the banner is unavailable.
    """
    try:
        banner_ansi = _BANNER_PATH.read_text().strip("\n")
    except OSError:
        return None
    if not banner_ansi:
        return None
    return Text.from_ansi(banner_ansi)


def _load_freeact_version() -> str:
    """Resolve the installed freeact package version via metadata.

    Local build metadata (the `+...` suffix) is omitted for display because it
    can reflect an editable-install build identifier rather than the currently
    checked-out source state.
    """
    try:
        version = package_version("freeact")
    except PackageNotFoundError:
        return "unknown"
    return version.split("+", 1)[0]


def _format_display_cwd(cwd: Path | None = None, home: Path | None = None) -> str:
    """Format cwd for UI display, preferring `~/` when under home directory."""
    resolved_cwd = (cwd or Path.cwd()).expanduser().resolve()
    resolved_home = (home or Path.home()).expanduser().resolve()
    try:
        relative = resolved_cwd.relative_to(resolved_home)
    except ValueError:
        return str(resolved_cwd)
    relative_text = relative.as_posix()
    if not relative_text:
        return "~/"
    return f"~/{relative_text}"


class ConversationView(VerticalScroll):
    """Scrollable conversation container with banner and collapse management."""

    DEFAULT_CSS = """
    ConversationView {
        height: 1fr;
        align-vertical: bottom;
        scrollbar-size: 1 1;
    }
    #banner-top-spacer {
        height: 1;
    }
    #banner {
        padding: 0 1;
    }
    #banner-spacer {
        height: 1;
    }
    #banner-metadata {
        padding: 0 1;
        color: $text-muted;
    }
    #banner-divider {
        height: 1;
        border-top: solid $panel-lighten-1;
        margin: 0 1;
    }
    Collapsible.-collapsed {
        padding: 0 0 0 1;
        border-top: none;
    }
    Collapsible.-collapsed CollapsibleTitle {
        padding: 0 1;
        background: transparent;
    }
    .exec-output-box RichLog {
        height: auto;
        max-height: 50;
    }
    Markdown MarkdownBlock {
        link-style: underline;
        link-background: transparent;
        link-style-hover: bold underline;
        link-background-hover: transparent;
    }
    .error-box {
        border-top: solid $error;
    }
    .error-text {
        color: $error;
    }
    .tool-call-content {
        height: auto;
    }
    .tool-trace-container {
        height: auto;
    }
    """

    def __init__(self, working_dir: Path | None = None, id: str | None = None) -> None:
        """Initialize the conversation view.

        Args:
            working_dir: Directory shown in the banner metadata. Defaults to
                the current directory.
            id: DOM identifier for this container.
        """
        super().__init__(id=id)
        self._banner = _load_banner()
        self._version = _load_freeact_version()
        self._display_cwd = _format_display_cwd(working_dir)
        self.policy = CollapsePolicy(schedule_scroll=self.schedule_scroll_to_latest)

    def compose(self) -> ComposeResult:
        if self._banner is not None:
            yield Static("", id="banner-top-spacer")
            yield Static(self._banner, id="banner")
            yield Static("", id="banner-spacer")
        yield Static(f"Version: {self._version}\n{self._display_cwd}", id="banner-metadata")
        yield Static("", id="banner-divider")

    def scroll_to_latest(self) -> None:
        """Position the conversation viewport at the latest content."""
        self.scroll_end(animate=False)

    def schedule_scroll_to_latest(self) -> None:
        """Re-apply bottom alignment after the next layout refresh."""
        self.call_after_refresh(self.scroll_to_latest)

    async def mount_widgets(self, *widgets: Widget, target: Widget | None = None) -> None:
        """Mount widgets into a target container and scroll to the bottom.

        Args:
            *widgets: Widgets to mount in order.
            target: Container that owns the widgets. Defaults to the
                conversation root.
        """
        parent = target if target is not None else self
        for widget in widgets:
            await parent.mount(widget)
        self.scroll_end(animate=False)
        self.schedule_scroll_to_latest()

    async def mount_box(
        self,
        box: TrackedCollapsible,
        target: Widget | None = None,
        configured_collapsed: bool = False,
        force_expanded: bool = False,
    ) -> None:
        """Register a collapsible with the collapse policy and mount it.

        Args:
            box: Collapsible widget to track and mount.
            target: Container that owns the widget. Defaults to the
                conversation root.
            configured_collapsed: Initial configured collapsed state.
            force_expanded: Pin the widget expanded until released.
        """
        self.policy.register(box, configured_collapsed=configured_collapsed, force_expanded=force_expanded)
        await self.mount_widgets(box, target=target)

    def toggle_expand_all(self) -> None:
        """Flip the global expand-all override for all collapsibles."""
        self.policy.toggle_expand_all(list(self.query(Collapsible)))

    def on_tracked_collapsible_user_toggled(self, event: TrackedCollapsible.UserToggled) -> None:
        self.policy.record_manual_toggle(event.collapsible, collapsed=event.collapsed)
