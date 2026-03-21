_SHELL_OPERATORS = {"&&", "||", "|", ";"}

_KNOWN_SUBCOMMAND_TOOLS = frozenset(
    {
        "git",
        "pip",
        "docker",
        "kubectl",
        "npm",
        "yarn",
        "cargo",
        "go",
        "apt",
        "brew",
        "conda",
        "poetry",
        "uv",
        "make",
        "systemctl",
    }
)


def suggest_shell_pattern(command: str) -> str:
    """Suggest a glob pattern for a shell command.

    Uses `cmd subcmd *` heuristic for known multi-word commands,
    otherwise `cmd *`.
    """
    parts = command.split()
    if not parts:
        return "*"
    if len(parts) >= 2 and parts[0] in _KNOWN_SUBCOMMAND_TOOLS:
        return f"{parts[0]} {parts[1]} *"
    return f"{parts[0]} *"


def split_composite_command(command: str) -> list[str]:
    """Split a composite shell command on `&&`, `||`, `|`, and `;`.

    Respects quoting so that operators inside quotes are not split.

    Args:
        command: Shell command string, potentially with composite operators.

    Returns:
        List of individual sub-command strings.
    """
    result: list[str] = []
    current: list[str] = []
    i = 0
    in_single_quote = False
    in_double_quote = False

    while i < len(command):
        ch = command[i]

        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current.append(ch)
            i += 1
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(ch)
            i += 1
        elif in_single_quote or in_double_quote:
            current.append(ch)
            i += 1
        elif command[i : i + 2] in ("&&", "||"):
            part = "".join(current).strip()
            if part:
                result.append(part)
            current = []
            i += 2
        elif ch in ("|", ";"):
            part = "".join(current).strip()
            if part:
                result.append(part)
            current = []
            i += 1
        else:
            current.append(ch)
            i += 1

    part = "".join(current).strip()
    if part:
        result.append(part)

    return result
