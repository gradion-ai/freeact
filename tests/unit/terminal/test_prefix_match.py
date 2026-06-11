# Covers behavior-inventory.md sections: 20 (terminal UI: picker prefix matching)
import pytest

from freeact.terminal.screens import _find_prefix_match as find_prefix_match


@pytest.mark.parametrize(
    ("items", "prefix", "expected"),
    [
        (["aab", "abc", "bcd"], "a", (0, "a")),
        (["aab", "abc", "bcd"], "ab", (1, "ab")),
        (["aab", "abc", "bcd"], "abb", (1, "ab")),
        (["aab", "abc"], "z", None),
        (["Alpha", "beta"], "a", (0, "a")),
        (["aab", "abc"], "", None),
    ],
    ids=["single_char", "two_chars", "fallback", "no_match", "case_insensitive", "empty_prefix"],
)
def test_find_prefix_match(items: list[str], prefix: str, expected: tuple[int, str] | None) -> None:
    assert find_prefix_match(items, prefix) == expected
