import sys
from contextlib import contextmanager
from pathlib import Path
from typing import List


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
