def find_prefix_match(items: list[str], prefix: str) -> tuple[int, str] | None:
    """Find the first item starting with ``prefix`` (case-insensitive).

    If no item matches the full prefix, progressively shorter prefixes are
    tried so that a non-matching keystroke does not lose the current position.

    Args:
        items: List of strings to search.
        prefix: Current prefix buffer to match against.

    Returns:
        ``(index, effective_prefix)`` of the first match, or ``None`` when
        nothing matches even at length 1.
    """
    if not prefix:
        return None

    lower_items = [item.lower() for item in items]

    for length in range(len(prefix), 0, -1):
        candidate = prefix[:length].lower()
        for i, item in enumerate(lower_items):
            if item.startswith(candidate):
                return (i, prefix[:length])

    return None
