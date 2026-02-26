from freeact.terminal.prefix_match import find_prefix_match


def test_find_prefix_match_single_char() -> None:
    items = ["aab", "abc", "bcd"]
    result = find_prefix_match(items, "a")
    assert result == (0, "a")


def test_find_prefix_match_two_chars() -> None:
    items = ["aab", "abc", "bcd"]
    result = find_prefix_match(items, "ab")
    assert result == (1, "ab")


def test_find_prefix_match_fallback() -> None:
    items = ["aab", "abc", "bcd"]
    result = find_prefix_match(items, "abb")
    assert result == (1, "ab")


def test_find_prefix_match_no_match() -> None:
    items = ["aab", "abc"]
    result = find_prefix_match(items, "z")
    assert result is None


def test_find_prefix_match_case_insensitive() -> None:
    items = ["Alpha", "beta"]
    result = find_prefix_match(items, "a")
    assert result == (0, "a")


def test_find_prefix_match_empty_prefix() -> None:
    result = find_prefix_match(["aab", "abc"], "")
    assert result is None
