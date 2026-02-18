from freeact.terminal.legacy.interface import convert_at_references


def test_simple_path():
    assert convert_at_references("Look at @image.png") == "Look at <attachment>image.png</attachment>"


def test_multiple_paths():
    text = "@a.png and @b.jpg"
    assert convert_at_references(text) == "<attachment>a.png</attachment> and <attachment>b.jpg</attachment>"


def test_home_dir():
    assert convert_at_references("@~/images/pic.png") == "<attachment>~/images/pic.png</attachment>"


def test_no_at_references():
    text = "No file references here"
    assert convert_at_references(text) == text


def test_at_in_middle_of_sentence():
    text = "Describe @/tmp/photo.png please"
    assert convert_at_references(text) == "Describe <attachment>/tmp/photo.png</attachment> please"


def test_preserves_surrounding_text():
    text = "Start @file.png middle @other.jpg end"
    expected = "Start <attachment>file.png</attachment> middle <attachment>other.jpg</attachment> end"
    assert convert_at_references(text) == expected
