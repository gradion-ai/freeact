from freeact.agent.shell import split_composite_command, suggest_shell_pattern


class TestSplitCompositeCommand:
    """Tests for splitting composite shell commands."""

    def test_and_operator(self):
        assert split_composite_command("git add . && git commit -m 'msg'") == [
            "git add .",
            "git commit -m 'msg'",
        ]

    def test_or_operator(self):
        assert split_composite_command("cmd1 || cmd2") == ["cmd1", "cmd2"]

    def test_pipe_operator(self):
        assert split_composite_command("ls | grep foo") == ["ls", "grep foo"]

    def test_semicolon_operator(self):
        assert split_composite_command("cmd1 ; cmd2") == ["cmd1", "cmd2"]

    def test_quoted_operators(self):
        """Operators inside quotes should not be split."""
        assert split_composite_command("echo 'a && b'") == ["echo 'a && b'"]

    def test_no_operators(self):
        assert split_composite_command("git status") == ["git status"]

    def test_multiple_operators(self):
        assert split_composite_command("a && b | c ; d") == ["a", "b", "c", "d"]


class TestSuggestShellPattern:
    """Tests for shell pattern suggestion heuristics."""

    def test_command_with_subcommand(self):
        assert suggest_shell_pattern("git add /path/to/file.py") == "git add *"

    def test_single_token(self):
        assert suggest_shell_pattern("ls") == "ls *"

    def test_command_with_flags(self):
        assert suggest_shell_pattern("ls -la /tmp") == "ls *"

    def test_pip_install(self):
        assert suggest_shell_pattern("pip install pandas") == "pip install *"

    def test_docker_run(self):
        assert suggest_shell_pattern("docker run --rm ubuntu") == "docker run *"
