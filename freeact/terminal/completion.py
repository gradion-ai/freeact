"""File path completion with @ trigger for terminal input."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Iterator

from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document

if TYPE_CHECKING:
    from prompt_toolkit.completion import CompleteEvent


class AtFileCompleter(Completer):
    """File path completer triggered by `@` prefix.

    Activates when user types `@` followed by a path fragment, suggesting
    matching files and directories. Directories include a trailing separator.

    Example:
        ```
        "please read @src/" -> suggests files in src/
        "check @~/Documents/" -> suggests files in ~/Documents/
        ```
    """

    _AT_PATTERN = re.compile(r"@([^\s]*)$")

    def __init__(self, expanduser: bool = True) -> None:
        self._expanduser = expanduser
        self._path_completer = PathCompleter(expanduser=expanduser)

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterator[Completion]:
        """Yield file path completions when cursor follows `@`."""
        text_before_cursor = document.text_before_cursor

        match = self._AT_PATTERN.search(text_before_cursor)
        if match is None:
            return

        path_fragment = match.group(1)
        path_doc = Document(path_fragment, cursor_position=len(path_fragment))

        for completion in self._path_completer.get_completions(path_doc, complete_event):
            # Build full path to check if it's a directory
            full_path = path_fragment + completion.text
            if self._expanduser:
                full_path = os.path.expanduser(full_path)

            # Add trailing separator for directories
            text = completion.text
            if os.path.isdir(full_path) and not text.endswith(os.sep):
                text = text + os.sep

            yield Completion(
                text=text,
                start_position=completion.start_position,
                display=completion.display,
                display_meta=completion.display_meta,
                style=completion.style,
                selected_style=completion.selected_style,
            )
