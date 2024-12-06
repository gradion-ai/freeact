"""
from typing import ModuleType

from gradion.executor import ExecutionContainer

# from skill modules (api.py), create python code listings (always use / as path separator, because container is linux)
# then install the lib containing the skills in the kernel (via dependencies.txt)
# for checked out project i.e. development mode, directly mount components dir
# add function to create create container image and install deps (passed as args)


class CodeActContainer(ExecutionContainer):
    def __init__(self, skill_modules: list[ModuleType]):
        self.skill_modules = skill_modules

        async def __aenter__(self):
            for module in self.skill_modules:
                await super().__aenter__()
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            for module in self.skill_modules:
                await super().__aexit__(exc_type, exc_val, exc_tb)
"""
