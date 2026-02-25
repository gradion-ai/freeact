from pathlib import Path
from unittest.mock import patch

from pydantic_ai import BinaryContent

from freeact.preproc.attachments import preprocess_attachment_tags


def test_no_path_tags_returns_string():
    text = "Hello, no file references here"
    assert preprocess_attachment_tags(text) == text


def test_non_image_path_returns_string(tmp_path: Path):
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("hello")
    text = f'Check this <attachment path="{txt_file}"/>'
    assert preprocess_attachment_tags(text) == text


def test_image_path_returns_multimodal(tmp_path: Path):
    img_file = tmp_path / "pic.png"
    sentinel = BinaryContent(data=b"fake", media_type="image/png")

    with (
        patch("freeact.preproc.attachments.collect_images", return_value=[img_file]),
        patch("freeact.preproc.attachments.load_image", return_value=sentinel),
    ):
        text = f'Describe <attachment path="{img_file}"/>'
        result = preprocess_attachment_tags(text)

    assert isinstance(result, list)
    assert len(result) == 3
    assert f'Attachment path="{img_file}":' == result[0]
    assert result[1] is sentinel
    assert result[2] == text


def test_multiple_image_paths(tmp_path: Path):
    img1 = tmp_path / "a.png"
    img2 = tmp_path / "b.jpg"
    sentinel1 = BinaryContent(data=b"1", media_type="image/png")
    sentinel2 = BinaryContent(data=b"2", media_type="image/jpeg")

    with (
        patch("freeact.preproc.attachments.collect_images", side_effect=[[img1], [img2]]),
        patch("freeact.preproc.attachments.load_image", side_effect=[sentinel1, sentinel2]),
    ):
        text = f'Compare <attachment path="{img1}"/> and <attachment path="{img2}"/>'
        result = preprocess_attachment_tags(text)

    assert isinstance(result, list)
    # 2 images * (label + binary) + text = 5
    assert len(result) == 5
    assert result[4] == text


def test_home_dir_expansion(tmp_path: Path):
    sentinel = BinaryContent(data=b"fake", media_type="image/png")

    with (
        patch("freeact.preproc.attachments.collect_images", return_value=[tmp_path / "pic.png"]),
        patch("freeact.preproc.attachments.load_image", return_value=sentinel),
    ):
        text = '<attachment path="~/images/pic.png"/> describe this'
        result = preprocess_attachment_tags(text)

    assert isinstance(result, list)
