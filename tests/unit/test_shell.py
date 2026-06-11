# Covers behavior-inventory.md sections: 4 (shell command interception)
import pytest

from freeact.agent.shell import split_composite_command


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git add . && git commit -m 'msg'", ["git add .", "git commit -m 'msg'"]),
        ("cmd1 || cmd2", ["cmd1", "cmd2"]),
        ("ls | grep foo", ["ls", "grep foo"]),
        ("cmd1 ; cmd2", ["cmd1", "cmd2"]),
        ("echo 'a && b'", ["echo 'a && b'"]),
        ("git status", ["git status"]),
        ("a && b | c ; d", ["a", "b", "c", "d"]),
    ],
)
def test_split_composite_command(command: str, expected: list[str]) -> None:
    assert split_composite_command(command) == expected
