"""Prompt preprocessing: attachment extraction, skill expansion, and image handling."""

from collections.abc import Sequence

from pydantic_ai import UserContent

from freeact.preproc.attachments import parse_attachment_tags
from freeact.preproc.images import (
    DEFAULT_MAX_SIZE,
    IMAGE_EXTENSIONS,
    collect_images,
    load_image,
)
from freeact.preproc.skills import process_skill_tags


def parse_prompt(text: str, max_image_size: int = 1024) -> str | Sequence[UserContent]:
    """Preprocess a raw prompt: expand skill tags, then extract attachment references.

    Args:
        text: Raw user prompt text.
        max_image_size: Maximum dimension for images (downscaled if larger).

    Returns:
        Processed prompt as plain text or multimodal content list.
    """
    text = process_skill_tags(text)
    return parse_attachment_tags(text, max_image_size=max_image_size)


__all__ = [
    "DEFAULT_MAX_SIZE",
    "IMAGE_EXTENSIONS",
    "collect_images",
    "load_image",
    "parse_attachment_tags",
    "parse_prompt",
    "process_skill_tags",
]
