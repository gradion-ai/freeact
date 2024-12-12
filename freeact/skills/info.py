import importlib
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from inspect import getfile, getsource
from pathlib import Path, PurePath, PurePosixPath
from typing import List


@dataclass
class SkillInfo:
    module_name: str
    relative_path: PurePath
    source: str


def get_skill_infos(skill_modules: List[str], extension_paths: List[Path]) -> List[SkillInfo]:
    with extended_sys_path(extension_paths):
        return [get_skill_info(skill_module) for skill_module in skill_modules]


def get_skill_info(skill_module: str) -> SkillInfo:
    module = importlib.import_module(skill_module)
    module_path = Path(getfile(module))

    rel_scope = PurePosixPath(skill_module.replace(".", "/"))

    if module_path.name == "__init__.py":
        rel_path = rel_scope / "__init__.py"
    else:
        rel_path = rel_scope.with_suffix(".py")

    try:
        module_source = getsource(module)
    except OSError:
        module_source = ""

    return SkillInfo(module_name=module.__name__, relative_path=rel_path, source=module_source)


@contextmanager
def extended_sys_path(paths: Path | List[Path]):
    """
    Context manager to temporarily extend `sys.path` with given `paths`.

    This is an atomic operation in asyncio.
    """
    if isinstance(paths, Path):
        paths = [paths]

    extension_path = [str(Path(p).resolve()) for p in paths]
    original_path = sys.path.copy()

    try:
        sys.path = extension_path + sys.path
        yield
    finally:
        sys.path = original_path
