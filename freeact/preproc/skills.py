"""Skill tag preprocessing: `<skill>` tag expansion with frontmatter stripping."""

import re
from pathlib import Path

_SKILL_TAG_PATTERN = re.compile(r'<skill\s+path="([^"]+)">(.*?)</skill>', re.DOTALL)
_ARGUMENTS_PLACEHOLDER = "$ARGUMENTS"


def strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from skill content.

    Args:
        content: Raw skill file content, possibly starting with `---` delimited frontmatter.

    Returns:
        Content with frontmatter removed, or the original content if no frontmatter is present.
    """
    if not content.startswith("---"):
        return content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return content
    return parts[2].lstrip("\n")


def process_skill_tags(text: str) -> str:
    """Expand `<skill path="...">arguments</skill>` tags by inlining skill file content.

    Args:
        text: Prompt text potentially containing `<skill>` tags.

    Returns:
        Text with skill tags replaced by their file content.
    """

    def _replace_skill(match: re.Match[str]) -> str:
        path = Path(match.group(1))
        args = match.group(2).strip()

        if not path.exists():
            return f"[Error: skill not found: {path}]"

        content = strip_frontmatter(path.read_text())

        if args:
            if _ARGUMENTS_PLACEHOLDER in content:
                content = content.replace(_ARGUMENTS_PLACEHOLDER, args)
            else:
                content = f"{content}\n\nARGUMENTS: {args}"

        return content

    return _SKILL_TAG_PATTERN.sub(_replace_skill, text)
