from freeact.agent.shell import extract_shell_commands, split_composite_command, suggest_shell_pattern


class TestExtractShellCommands:
    """Tests for extracting shell commands from IPython cells."""

    def test_bang_command(self):
        assert extract_shell_commands("!git status") == ["git status"]

    def test_double_bang_command(self):
        assert extract_shell_commands("!!git status") == ["git status"]

    def test_bash_cell_magic(self):
        code = "%%bash\ngit status\necho hello"
        result = extract_shell_commands(code)
        assert result == ["git status\necho hello\n"]

    def test_mixed_python_and_shell(self):
        code = "x = 1\n!git status\ny = 2"
        result = extract_shell_commands(code)
        assert result == ["git status"]

    def test_pure_python(self):
        code = "x = 1\ny = x + 2\nprint(y)"
        result = extract_shell_commands(code)
        assert result == []

    def test_multiple_bang_commands(self):
        code = "!git status\n!pip install pandas"
        result = extract_shell_commands(code)
        assert result == ["git status", "pip install pandas"]


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
