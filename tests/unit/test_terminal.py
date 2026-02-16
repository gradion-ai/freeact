from freeact.terminal.interface import convert_at_references


def test_simple_path():
    assert convert_at_references("Look at @image.png") == "Look at <path>image.png</path>"


def test_multiple_paths():
    text = "@a.png and @b.jpg"
    assert convert_at_references(text) == "<path>a.png</path> and <path>b.jpg</path>"


def test_home_dir():
    assert convert_at_references("@~/images/pic.png") == "<path>~/images/pic.png</path>"


def test_no_at_references():
    text = "No file references here"
    assert convert_at_references(text) == text


def test_at_in_middle_of_sentence():
    text = "Describe @/tmp/photo.png please"
    assert convert_at_references(text) == "Describe <path>/tmp/photo.png</path> please"


def test_preserves_surrounding_text():
    text = "Start @file.png middle @other.jpg end"
    expected = "Start <path>file.png</path> middle <path>other.jpg</path> end"
    assert convert_at_references(text) == expected
