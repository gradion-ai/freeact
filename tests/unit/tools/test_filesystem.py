import io
import os
from pathlib import Path

import pytest
from PIL import Image as PILImage

from freeact.tools.filesystem import (
    DEFAULT_MAX_IMAGE_SIZE,
    _guess_media_type,
    _load_image,
    _load_media,
    detect_line_ending,
    edit_text_file,
    fuzzy_find_text,
    normalize_for_fuzzy_match,
    normalize_to_lf,
    read_text_file,
    resolve_path,
    restore_line_endings,
    strip_bom,
    write_text_file,
)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("image.png", "image/png"),
        ("photo.jpg", "image/jpeg"),
        ("audio.mp3", "audio/mpeg"),
        ("sound.wav", "audio/wav"),
        ("doc.pdf", "application/pdf"),
        ("file.xyz123", None),
        ("script.py", None),
        ("data.csv", None),
        ("README.md", None),
        ("page.html", None),
        ("config.json", None),
    ],
)
def test_guess_media_type(filename: str, expected: str | None) -> None:
    assert _guess_media_type(Path(filename)) == expected


def save_image(path: Path, size: int, color: str) -> None:
    PILImage.new("RGB", (size, size), color=color).save(path)


class TestLoadImage:
    def test_small_image_not_downscaled(self, tmp_path: Path) -> None:
        path = tmp_path / "small.png"
        save_image(path, 100, "red")
        data = _load_image(path, "image/png", DEFAULT_MAX_IMAGE_SIZE)
        loaded = PILImage.open(path)
        assert loaded.width == 100
        assert len(data) > 0

    def test_large_image_downscaled(self, tmp_path: Path) -> None:
        path = tmp_path / "large.png"
        save_image(path, 2000, "blue")
        data = _load_image(path, "image/png", 512)
        result = PILImage.open(io.BytesIO(data))
        assert result.width <= 512
        assert result.height <= 512


class TestLoadMedia:
    def test_image_delegates_to_load_image(self, tmp_path: Path) -> None:
        path = tmp_path / "test.png"
        save_image(path, 50, "green")
        data = _load_media(path, "image/png")
        assert len(data) > 0

    def test_non_image_reads_raw(self, tmp_path: Path) -> None:
        path = tmp_path / "audio.mp3"
        path.write_bytes(b"fake mp3 data")
        data = _load_media(path, "audio/mpeg")
        assert data == b"fake mp3 data"


class TestResolvePath:
    @pytest.mark.parametrize(
        ("path", "base", "expected"),
        [
            ("src/main.py", "/home/user/project", "/home/user/project/src/main.py"),
            ("/tmp/file.txt", "/home/user", "/tmp/file.txt"),
            ("./src/../src/main.py", "/home/user/project", "/home/user/project/src/main.py"),
        ],
    )
    def test_resolution(self, path: str, base: str, expected: str) -> None:
        assert resolve_path(path, base) == expected

    def test_home_expansion(self) -> None:
        result = resolve_path("~/file.txt", "/home/user")
        assert os.path.expanduser("~") in result


class TestFuzzyMatching:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("\u201chello\u201d", '"hello"'),
            ("a\u2014b", "a-b"),
            ("a\u00a0b", "a b"),
            ("hello   \nworld  ", "hello\nworld"),
        ],
    )
    def test_normalize(self, text: str, expected: str) -> None:
        assert normalize_for_fuzzy_match(text) == expected

    def test_fuzzy_find_exact(self) -> None:
        result = fuzzy_find_text("hello world", "world")
        assert result.found
        assert not result.used_fuzzy_match
        assert result.index == 6

    def test_fuzzy_find_with_smart_quotes(self) -> None:
        result = fuzzy_find_text('say "hello"', "say \u201chello\u201d")
        assert result.found
        assert result.used_fuzzy_match

    def test_fuzzy_find_not_found(self) -> None:
        assert not fuzzy_find_text("hello world", "goodbye").found

    @pytest.mark.parametrize(
        ("text", "expected_bom", "expected_text"),
        [("\ufeffhello", "\ufeff", "hello"), ("hello", "", "hello")],
    )
    def test_strip_bom(self, text: str, expected_bom: str, expected_text: str) -> None:
        assert strip_bom(text) == (expected_bom, expected_text)


class TestLineEndings:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [("a\nb\n", "\n"), ("a\r\nb\r\n", "\r\n"), ("hello", "\n")],
    )
    def test_detect(self, text: str, expected: str) -> None:
        assert detect_line_ending(text) == expected

    def test_normalize_to_lf(self) -> None:
        assert normalize_to_lf("a\r\nb\r") == "a\nb\n"

    @pytest.mark.parametrize(
        ("ending", "expected"),
        [("\r\n", "a\r\nb"), ("\n", "a\nb")],
    )
    def test_restore(self, ending: str, expected: str) -> None:
        assert restore_line_endings("a\nb", ending) == expected


class TestReadTextFile:
    def test_full_read(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3")
        result = read_text_file(str(f))
        assert "line1" in result
        assert "line3" in result

    def test_offset_limit(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\nline4\nline5")
        result = read_text_file(str(f), offset=2, limit=2)
        assert "line2" in result
        assert "line3" in result
        assert "line1" not in result
        assert "[Lines 2-3 of 5 total]" in result

    def test_offset_beyond_end(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("one line")
        with pytest.raises(ValueError, match="beyond end"):
            read_text_file(str(f), offset=100)


class TestWriteTextFile:
    def test_basic_write(self, tmp_path: Path) -> None:
        path = tmp_path / "output.txt"
        result = write_text_file(str(path), "hello world")
        assert "Successfully wrote" in result
        assert path.read_text() == "hello world"

    def test_parent_dir_creation(self, tmp_path: Path) -> None:
        path = tmp_path / "sub" / "dir" / "file.txt"
        write_text_file(str(path), "content")
        assert path.read_text() == "content"


class TestEditTextFile:
    def test_exact_match(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("DEBUG = True\nVERBOSE = False")
        result = edit_text_file(str(f), "DEBUG = True", "DEBUG = False")
        assert "Successfully replaced" in result
        assert f.read_text() == "DEBUG = False\nVERBOSE = False"

    def test_fuzzy_match(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text('say "hello"')
        result = edit_text_file(str(f), "say \u201chello\u201d", "say 'hi'")
        assert "Successfully replaced" in result

    def test_uniqueness_check(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\nx = 1")
        with pytest.raises(ValueError, match="2 occurrences"):
            edit_text_file(str(f), "x = 1", "x = 2")

    def test_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("hello world")
        with pytest.raises(ValueError, match="Could not find"):
            edit_text_file(str(f), "goodbye", "hi")

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            edit_text_file(str(tmp_path / "nonexistent.py"), "a", "b")

    def test_bom_preservation(self, tmp_path: Path) -> None:
        f = tmp_path / "bom.txt"
        f.write_bytes("\ufeffhello world".encode("utf-8"))
        edit_text_file(str(f), "hello", "goodbye")
        raw = f.read_bytes().decode("utf-8")
        assert raw.startswith("\ufeff")
        assert "goodbye world" in raw

    def test_crlf_preservation(self, tmp_path: Path) -> None:
        f = tmp_path / "crlf.txt"
        f.write_bytes(b"line1\r\nline2\r\nline3")
        edit_text_file(str(f), "line2", "replaced")
        raw = f.read_bytes()
        assert b"\r\n" in raw
        assert b"replaced" in raw

    def test_no_change_error(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("hello")
        with pytest.raises(ValueError, match="No changes"):
            edit_text_file(str(f), "hello", "hello")
