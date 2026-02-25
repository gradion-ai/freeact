"""User prompt parsing with `<attachment>` tag extraction."""

import re
from collections.abc import Sequence
from pathlib import Path

from pydantic_ai import UserContent

from freeact.preproc.images import collect_images, load_image

_ATTACHMENT_TAG_PATTERN = re.compile(r'<attachment\s+path="([^"]+)"\s*/>')


def preprocess_attachment_tags(text: str, max_image_size: int = 1024) -> str | Sequence[UserContent]:
    """Resolve `<attachment path="..."/>` tags to multimodal content.

    Scans `text` for attachment tags, collects image files from the referenced
    paths (a path may point to a single file or a directory), and loads each
    image as binary content. The original text is preserved as the last element
    of the returned list.

    When no attachment tags are found, or none of the referenced paths contain
    images, the original text is returned unchanged as a plain string.

    Args:
        text: Prompt text potentially containing `<attachment path="..."/>` tags.
        max_image_size: Maximum dimension in pixels. Images exceeding this are
            downscaled while preserving aspect ratio.

    Returns:
        The original text when no images are found, or a list of
            `[label, image, ..., label, image, text]` entries where each label is a
            string like `Attachment path="...":` and each image is a `BinaryContent`
            object.

    Note:
        Directory paths include all images in that directory (non-recursive).
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
