"""Image handling utilities with downscaling support."""

import io
from pathlib import Path

from PIL import Image
from pydantic_ai import BinaryContent

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
DEFAULT_MAX_SIZE = 1024


def collect_images(path: Path) -> list[Path]:
    """Collect image files from a path (file or directory)."""
    if path.is_file():
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            return [path]
        return []

    if path.is_dir():
        return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)

    return []


def load_image(path: Path, max_size: int = DEFAULT_MAX_SIZE) -> BinaryContent:
    """Load image, downscaling if either dimension exceeds max_size."""
    with Image.open(path) as img:
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), resample=Image.Resampling.LANCZOS)
            fmt = img.format or "PNG"
            buf = io.BytesIO()
            img.save(buf, format=fmt)
            return BinaryContent(data=buf.getvalue(), media_type=f"image/{fmt.lower()}")
        else:
            return BinaryContent.from_path(path)
