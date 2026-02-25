"""Combined prompt preprocessing pipeline."""

from collections.abc import Sequence

from pydantic_ai import UserContent

from freeact.preproc.attachments import preprocess_attachment_tags


def preprocess_prompt(text: str, max_image_size: int = 1024) -> str | Sequence[UserContent]:
    """Main preprocessing entry point. Transforms prompt text into agent-ready content.

    Currently delegates to
    [`preprocess_attachment_tags`][freeact.preproc.preprocess_attachment_tags]
    to resolve image attachments. Other tag types (e.g. `<skill>`) pass through
    unchanged for the agent to handle.

    Args:
        text: Prompt text, potentially containing `<attachment>` and `<skill>` tags.
        max_image_size: Maximum dimension for images (downscaled if larger).

    Returns:
        The original text if no images are found, or a multimodal content list
            with resolved image data.
    """
    return preprocess_attachment_tags(text, max_image_size=max_image_size)
