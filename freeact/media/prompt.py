"""User prompt parsing with `<attachment>` tag extraction."""

import re
from collections.abc import Sequence
from pathlib import Path

from pydantic_ai import UserContent

from freeact.media.images import collect_images, load_image

_ATTACHMENT_TAG_PATTERN = re.compile(r"<attachment>(.*?)</attachment>")


def parse_prompt(text: str, max_image_size: int = 1024) -> str | Sequence[UserContent]:
    """Extract `<attachment>...</attachment>` image references into multimodal content.

    Returns the original text unchanged if no images are found.
    Otherwise returns labeled images (as binary content) followed by text.

    Args:
        text: User prompt text with `<attachment>...</attachment>` references.
        max_image_size: Maximum dimension for images (downscaled if larger).

    Note:
        Directory references include all images in that directory (non-recursive).
    """
    matches = list(_ATTACHMENT_TAG_PATTERN.finditer(text))
    if not matches:
        return text

    images: list[Path] = []
    for match in matches:
        resolved = Path(match.group(1)).expanduser()
        images.extend(collect_images(resolved))

    if not images:
        return text

    content: list[UserContent] = []
    for path in images:
        content.append(f'Attachment path="{path}":')
        content.append(load_image(path, max_size=max_image_size))
    content.append(text)

    return content
