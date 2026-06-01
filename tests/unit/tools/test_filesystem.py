import os
from pathlib import Path

import pytest

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


class TestGuessMediaType:
    def test_png(self) -> None:
        assert _guess_media_type(Path("image.png")) == "image/png"

    def test_jpeg(self) -> None:
        assert _guess_media_type(Path("photo.jpg")) == "image/jpeg"

    def test_mp3(self) -> None:
        assert _guess_media_type(Path("audio.mp3")) == "audio/mpeg"

    def test_wav_correction(self) -> None:
        result = _guess_media_type(Path("sound.wav"))
        assert result == "audio/wav"

    def test_pdf(self) -> None:
        assert _guess_media_type(Path("doc.pdf")) == "application/pdf"

    def test_unsupported(self) -> None:
        assert _guess_media_type(Path("data.xyz123")) is None

    def test_unknown_extension(self) -> None:
        assert _guess_media_type(Path("file.xyz123")) is None

    def test_python_file(self) -> None:
        assert _guess_media_type(Path("script.py")) is None

    def test_csv_not_media(self) -> None:
        assert _guess_media_type(Path("data.csv")) is None

    def test_markdown_not_media(self) -> None:
        assert _guess_media_type(Path("README.md")) is None

    def test_html_not_media(self) -> None:
        assert _guess_media_type(Path("page.html")) is None

    def test_json_not_media(self) -> None:
        assert _guess_media_type(Path("config.json")) is None


class TestLoadImage:
    def test_small_image_not_downscaled(self, tmp_path: Path) -> None:
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (100, 100), color="red")
        path = tmp_path / "small.png"
        img.save(path)

        data = _load_image(path, "image/png", DEFAULT_MAX_IMAGE_SIZE)
        loaded = PILImage.open(path)
        assert loaded.width == 100
        assert len(data) > 0

    def test_large_image_downscaled(self, tmp_path: Path) -> None:
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (2000, 2000), color="blue")
        path = tmp_path / "large.png"
        img.save(path)

        data = _load_image(path, "image/png", 512)
        import io

        result = PILImage.open(io.BytesIO(data))
        assert result.width <= 512
        assert result.height <= 512


class TestLoadMedia:
    def test_image_delegates_to_load_image(self, tmp_path: Path) -> None:
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (50, 50), color="green")
        path = tmp_path / "test.png"
        img.save(path)

        data = _load_media(path, "image/png")
        assert len(data) > 0

    def test_non_image_reads_raw(self, tmp_path: Path) -> None:
        path = tmp_path / "audio.mp3"
        path.write_bytes(b"fake mp3 data")

        data = _load_media(path, "audio/mpeg")
        assert data == b"fake mp3 data"


class TestResolvePath:
    def test_relative_path(self) -> None:
        result = resolve_path("src/main.py", "/home/user/project")
        assert result == "/home/user/project/src/main.py"

    def test_absolute_path(self) -> None:
        result = resolve_path("/tmp/file.txt", "/home/user")
        assert result == "/tmp/file.txt"

    def test_home_expansion(self) -> None:
        result = resolve_path("~/file.txt", "/home/user")
        assert os.path.expanduser("~") in result

    def test_dot_normalization(self) -> None:
        result = resolve_path("./src/../src/main.py", "/home/user/project")
        assert result == "/home/user/project/src/main.py"


class TestFuzzyMatching:
    def test_normalize_smart_quotes(self) -> None:
        assert normalize_for_fuzzy_match("\u201chello\u201d") == '"hello"'

    def test_normalize_em_dash(self) -> None:
        assert normalize_for_fuzzy_match("a\u2014b") == "a-b"

    def test_normalize_nbsp(self) -> None:
        assert normalize_for_fuzzy_match("a\u00a0b") == "a b"

    def test_normalize_trailing_whitespace(self) -> None:
        assert normalize_for_fuzzy_match("hello   \nworld  ") == "hello\nworld"

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
        result = fuzzy_find_text("hello world", "goodbye")
        assert not result.found

    def test_strip_bom_present(self) -> None:
        bom, text = strip_bom("\ufeffhello")
        assert bom == "\ufeff"
        assert text == "hello"

    def test_strip_bom_absent(self) -> None:
        bom, text = strip_bom("hello")
        assert bom == ""
        assert text == "hello"


class TestLineEndings:
    def test_detect_lf(self) -> None:
        assert detect_line_ending("a\nb\n") == "\n"

    def test_detect_crlf(self) -> None:
        assert detect_line_ending("a\r\nb\r\n") == "\r\n"

    def test_detect_no_newlines(self) -> None:
        assert detect_line_ending("hello") == "\n"

    def test_normalize_to_lf(self) -> None:
        assert normalize_to_lf("a\r\nb\r") == "a\nb\n"

    def test_restore_crlf(self) -> None:
        assert restore_line_endings("a\nb", "\r\n") == "a\r\nb"

    def test_restore_lf_noop(self) -> None:
        assert restore_line_endings("a\nb", "\n") == "a\nb"


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
