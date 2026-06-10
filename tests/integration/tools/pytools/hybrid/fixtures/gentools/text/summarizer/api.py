"""Text summarization tool."""


def run(text: str, max_length: int = 100) -> str:
    """Summarize text to a shorter version.

    Args:
        text: Input text to summarize.
        max_length: Maximum output length.

    Returns:
        Summarized text.
    """
    return text[:max_length]
