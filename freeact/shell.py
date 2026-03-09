import ast

from IPython.core.inputtransformer2 import TransformerManager

_transformer = TransformerManager()

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


def extract_shell_commands(code: str) -> list[str]:
    """Extract shell commands from an IPython cell.

    Uses IPython's `TransformerManager` to transform the cell, then
    parses the AST to find `get_ipython().system()`,
    `get_ipython().getoutput()`, and `get_ipython().run_cell_magic("bash", ...)`
    calls.

    Args:
        code: IPython cell source code.

    Returns:
        List of shell command strings found in the cell.
    """
    if "!" not in code and "%%bash" not in code:
        return []

    transformed = _transformer.transform_cell(code)
    try:
        tree = ast.parse(transformed)
    except SyntaxError:
        return []

    commands: list[str] = []
    for node in ast.walk(tree):
        match node:
            case ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(attr=attr),
                    args=args,
                )
            ) if attr in ("system", "getoutput"):
                if args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
                    commands.append(args[0].value)
            case ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(attr="run_cell_magic"),
                    args=args,
                )
            ):
                if (
                    len(args) >= 3
                    and isinstance(args[0], ast.Constant)
                    and args[0].value == "bash"
                    and isinstance(args[2], ast.Constant)
                    and isinstance(args[2].value, str)
                ):
                    commands.append(args[2].value)

    return commands


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
