"""Initialize .freeact/ directory from templates."""

import shutil
from importlib.resources import as_file, files
from pathlib import Path


def init_config(working_dir: Path | None = None) -> None:
    """Initialize `.freeact/` config directory from templates.

    Copies template files that don't already exist, preserving user modifications.

    Args:
        working_dir: Base directory. Defaults to current working directory.
    """
    working_dir = working_dir or Path.cwd()
    freeact_dir = working_dir / ".freeact"

    template_files = files("freeact.agent.config").joinpath("templates")

    with as_file(template_files) as template_dir:
        for template_file in template_dir.rglob("*"):
            if not template_file.is_file():
                continue

            relative = template_file.relative_to(template_dir)
            target = freeact_dir / relative

            if target.exists():
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template_file, target)

    # Create plans directory
    plans_dir = freeact_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)

    # Create generated directory
    (freeact_dir / "generated").mkdir(parents=True, exist_ok=True)
