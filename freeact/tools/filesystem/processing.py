import difflib
import io
import mimetypes
import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from PIL import Image as PILImage
from pydantic_ai.messages import AudioMediaType, ImageMediaType, VideoMediaType

# Only image, audio, video, and PDF are treated as binary media.
# All other file types (including text-based document formats like
# csv, html, markdown) are read as UTF-8 text.
SUPPORTED_MEDIA_TYPES: frozenset[str] = frozenset(
    get_args(ImageMediaType) + get_args(AudioMediaType) + get_args(VideoMediaType) + ("application/pdf",)
)
IMAGE_MEDIA_TYPES: frozenset[str] = frozenset(get_args(ImageMediaType))

# Corrections for stdlib mimetypes mismatches with pydantic-ai
_MIME_CORRECTIONS: dict[str, str] = {"audio/x-wav": "audio/wav"}

DEFAULT_MAX_IMAGE_SIZE: int = 1024


# --- Media utilities ---


def _guess_media_type(path: Path) -> str | None:
    """Return MIME type if path is a supported media file, else None."""
    mime, _ = mimetypes.guess_type(str(path))
    if mime is None:
        return None
    mime = _MIME_CORRECTIONS.get(mime, mime)
    return mime if mime in SUPPORTED_MEDIA_TYPES else None


def _load_image(path: Path, media_type: str, max_size: int) -> bytes:
    """Load image with optional downscaling, returning raw bytes."""
    with PILImage.open(path) as img:
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), resample=PILImage.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format=media_type.split("/")[1].upper())
            return buf.getvalue()
    return path.read_bytes()


def _load_media(path: Path, media_type: str, max_image_size: int = DEFAULT_MAX_IMAGE_SIZE) -> bytes:
    """Load any supported media file as raw bytes."""
    if media_type in IMAGE_MEDIA_TYPES:
        return _load_image(path, media_type, max_image_size)
    return path.read_bytes()


# --- Edit/diff utilities ---


def detect_line_ending(content: str) -> str:
    crlf_idx = content.find("\r\n")
    lf_idx = content.find("\n")
    if lf_idx == -1:
        return "\n"
    if crlf_idx == -1:
        return "\n"
    return "\r\n" if crlf_idx < lf_idx else "\n"


def normalize_to_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def restore_line_endings(text: str, ending: str) -> str:
    if ending == "\r\n":
        return text.replace("\n", "\r\n")
    return text


def normalize_for_fuzzy_match(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    # Strip trailing whitespace per line
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Smart single quotes -> '
    for ch in "\u2018\u2019\u201a\u201b":
        text = text.replace(ch, "'")
    # Smart double quotes -> "
    for ch in "\u201c\u201d\u201e\u201f":
        text = text.replace(ch, '"')
    # Various dashes/hyphens -> -
    for ch in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212":
        text = text.replace(ch, "-")
    # Special spaces -> regular space
    for ch in "\u00a0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000":
        text = text.replace(ch, " ")
    return text


@dataclass
class FuzzyMatchResult:
    found: bool
    index: int
    match_length: int
    used_fuzzy_match: bool
    content_for_replacement: str


def fuzzy_find_text(content: str, old_text: str) -> FuzzyMatchResult:
    # Try exact match first
    exact_index = content.find(old_text)
    if exact_index != -1:
        return FuzzyMatchResult(
            found=True,
            index=exact_index,
            match_length=len(old_text),
            used_fuzzy_match=False,
            content_for_replacement=content,
        )

    # Try fuzzy match
    fuzzy_content = normalize_for_fuzzy_match(content)
    fuzzy_old_text = normalize_for_fuzzy_match(old_text)
    fuzzy_index = fuzzy_content.find(fuzzy_old_text)

    if fuzzy_index == -1:
        return FuzzyMatchResult(
            found=False,
            index=-1,
            match_length=0,
            used_fuzzy_match=False,
            content_for_replacement=content,
        )

    return FuzzyMatchResult(
        found=True,
        index=fuzzy_index,
        match_length=len(fuzzy_old_text),
        used_fuzzy_match=True,
        content_for_replacement=fuzzy_content,
    )


def strip_bom(content: str) -> tuple[str, str]:
    """Return (bom, text) -- bom is the BOM character if present, else empty string."""
    if content.startswith("\ufeff"):
        return ("\ufeff", content[1:])
    return ("", content)


@dataclass
class DiffResult:
    diff: str
    first_changed_line: int | None


def generate_diff_string(
    old_content: str,
    new_content: str,
    context_lines: int = 4,
) -> DiffResult:
    old_lines = old_content.split("\n")
    new_lines = new_content.split("\n")

    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    opcodes = sm.get_opcodes()

    max_line_num = max(len(old_lines), len(new_lines))
    line_num_width = len(str(max_line_num))

    output: list[str] = []
    old_line_num = 1
    new_line_num = 1
    last_was_change = False
    first_changed_line: int | None = None

    for i, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        if tag in ("replace", "delete", "insert"):
            if first_changed_line is None:
                first_changed_line = new_line_num

            if tag in ("replace", "delete"):
                for idx in range(i1, i2):
                    ln = str(old_line_num).rjust(line_num_width)
                    output.append(f"-{ln} {old_lines[idx]}")
                    old_line_num += 1

            if tag in ("replace", "insert"):
                for idx in range(j1, j2):
                    ln = str(new_line_num).rjust(line_num_width)
                    output.append(f"+{ln} {new_lines[idx]}")
                    new_line_num += 1

            last_was_change = True
        else:
            # equal
            raw = old_lines[i1:i2]
            next_is_change = i < len(opcodes) - 1 and opcodes[i + 1][0] != "equal"

            if last_was_change or next_is_change:
                if last_was_change and next_is_change:
                    # Between two changes: show trailing + leading context with ellipsis
                    if len(raw) <= context_lines * 2:
                        # Small enough to show all
                        for line in raw:
                            ln = str(old_line_num).rjust(line_num_width)
                            output.append(f" {ln} {line}")
                            old_line_num += 1
                            new_line_num += 1
                    else:
                        # Show trailing context from previous change
                        for line in raw[:context_lines]:
                            ln = str(old_line_num).rjust(line_num_width)
                            output.append(f" {ln} {line}")
                            old_line_num += 1
                            new_line_num += 1
                        # Ellipsis for skipped lines
                        skipped = len(raw) - context_lines * 2
                        output.append(f" {''.rjust(line_num_width)} ...")
                        old_line_num += skipped
                        new_line_num += skipped
                        # Show leading context for next change
                        for line in raw[-context_lines:]:
                            ln = str(old_line_num).rjust(line_num_width)
                            output.append(f" {ln} {line}")
                            old_line_num += 1
                            new_line_num += 1
                else:
                    lines_to_show = raw
                    skip_start = 0
                    skip_end = 0

                    if not last_was_change:
                        # Show only last N lines as leading context
                        skip_start = max(0, len(raw) - context_lines)
                        lines_to_show = raw[skip_start:]

                    if not next_is_change and len(lines_to_show) > context_lines:
                        # Show only first N lines as trailing context
                        skip_end = len(lines_to_show) - context_lines
                        lines_to_show = lines_to_show[:context_lines]

                    if skip_start > 0:
                        output.append(f" {''.rjust(line_num_width)} ...")
                        old_line_num += skip_start
                        new_line_num += skip_start

                    for line in lines_to_show:
                        ln = str(old_line_num).rjust(line_num_width)
                        output.append(f" {ln} {line}")
                        old_line_num += 1
                        new_line_num += 1

                    if skip_end > 0:
                        output.append(f" {''.rjust(line_num_width)} ...")
                        old_line_num += skip_end
                        new_line_num += skip_end
            else:
                # Skip entirely
                count = i2 - i1
                old_line_num += count
                new_line_num += count

            last_was_change = False

    return DiffResult(diff="\n".join(output), first_changed_line=first_changed_line)


def resolve_path(file_path: str, cwd: str) -> str:
    """Resolve a file path relative to cwd. Handles ~ expansion and absolute paths."""
    expanded = os.path.expanduser(file_path)
    if os.path.isabs(expanded):
        return expanded
    return os.path.normpath(os.path.join(cwd, expanded))


# --- File operations ---


def read_text_file(
    path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> str:
    """Read a text file with optional offset/limit slicing.

    Args:
        path: Absolute file path.
        offset: 1-indexed line number to start reading from.
        limit: Maximum number of lines to read.

    Returns:
        File content as text, with metadata line when offset/limit used.
    """
    with open(path, encoding="utf-8") as f:
        text_content = f.read()

    all_lines = text_content.split("\n")
    total_lines = len(all_lines)

    # Apply offset (1-indexed)
    start_line = max(0, offset - 1) if offset else 0

    if start_line >= total_lines:
        raise ValueError(f"Offset {offset} is beyond end of file ({total_lines} lines total)")

    # Apply limit
    if limit is not None:
        selected = all_lines[start_line : start_line + limit]
    else:
        selected = all_lines[start_line:]

    result = "\n".join(selected)

    # Add metadata when offset/limit used
    if offset is not None or limit is not None:
        start_display = start_line + 1
        end_display = start_line + len(selected)
        result += f"\n\n[Lines {start_display}-{end_display} of {total_lines} total]"

    return result


def write_text_file(path: str, content: str) -> str:
    """Write text content to a file, creating parent directories if needed.

    Args:
        path: Absolute file path.
        content: Text content to write.

    Returns:
        Success message with byte count.
    """
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Successfully wrote {len(content)} bytes"


def edit_text_file(path: str, old_text: str, new_text: str) -> str:
    """Find and replace text in a file with BOM/line-ending preservation.

    Args:
        path: Absolute file path.
        old_text: Text to find (must appear exactly once).
        new_text: Replacement text.

    Returns:
        Success message with diff and first changed line.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    if not os.access(path, os.R_OK | os.W_OK):
        raise PermissionError(f"File not readable/writable: {path}")

    with open(path, "rb") as f:
        raw_content = f.read().decode("utf-8")

    bom, content = strip_bom(raw_content)
    original_ending = detect_line_ending(content)
    normalized_content = normalize_to_lf(content)
    normalized_old_text = normalize_to_lf(old_text)
    normalized_new_text = normalize_to_lf(new_text)

    # Find old text (exact first, then fuzzy)
    match_result = fuzzy_find_text(normalized_content, normalized_old_text)

    if not match_result.found:
        raise ValueError(
            "Could not find the exact text. " "The old text must match exactly including all whitespace and newlines."
        )

    # Count occurrences using fuzzy-normalized content
    fuzzy_content = normalize_for_fuzzy_match(normalized_content)
    fuzzy_old_text = normalize_for_fuzzy_match(normalized_old_text)
    occurrences = len(fuzzy_content.split(fuzzy_old_text)) - 1

    if occurrences > 1:
        raise ValueError(
            f"Found {occurrences} occurrences of the text. "
            "The text must be unique. Please provide more context to make it unique."
        )

    # Perform replacement
    base_content = match_result.content_for_replacement
    new_content = (
        base_content[: match_result.index]
        + normalized_new_text
        + base_content[match_result.index + match_result.match_length :]
    )

    if base_content == new_content:
        raise ValueError("No changes made. The replacement produced identical content.")

    final_content = bom + restore_line_endings(new_content, original_ending)
    with open(path, "wb") as f:
        f.write(final_content.encode("utf-8"))

    diff_result = generate_diff_string(base_content, new_content)
    parts = ["Successfully replaced text."]
    if diff_result.diff:
        parts.append(diff_result.diff)
    if diff_result.first_changed_line is not None:
        parts.append(f"First changed line: {diff_result.first_changed_line}")
    return "\n\n".join(parts)
