import importlib
from dataclasses import dataclass
from inspect import getfile, getsource
from pathlib import Path, PurePath, PurePosixPath


@dataclass
class SkillInfo:
    module_name: str
    relative_path: PurePath
    source: str


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
