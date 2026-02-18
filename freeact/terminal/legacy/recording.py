from pathlib import Path

import aiofiles
from ipybox.utils import arun
from rich.console import Console

CONVERSATION_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
{svg}
</body>
</html>
"""


async def save_conversation(console: Console, record_dir: Path, record_title: str) -> None:
    """Save recorded console output as SVG and HTML files.

    Creates `conversation.svg` and `conversation.html` in the target directory.

    Args:
        console: Rich Console with recording enabled.
        record_dir: Directory to save output files (created if missing).
        record_title: Title displayed in the SVG recording.
    """
    record_dir.mkdir(parents=True, exist_ok=True)

    svg_path = record_dir / "conversation.svg"
    html_path = record_dir / "conversation.html"

    await arun(console.save_svg, str(svg_path), title=record_title)

    async with aiofiles.open(svg_path, "r") as f:
        svg = await f.read()

    async with aiofiles.open(html_path, "w") as f:
        await f.write(CONVERSATION_HTML_TEMPLATE.format(title=record_title, svg=svg))
