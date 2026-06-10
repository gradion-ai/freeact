import pytest

from freeact.agent.shell import split_composite_command, suggest_shell_pattern


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


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git add /path/to/file.py", "git add *"),
        ("ls", "ls *"),
        ("ls -la /tmp", "ls *"),
        ("pip install pandas", "pip install *"),
        ("docker run --rm ubuntu", "docker run *"),
    ],
)
def test_suggest_shell_pattern(command: str, expected: str) -> None:
    assert suggest_shell_pattern(command) == expected
