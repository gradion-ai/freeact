from dataclasses import dataclass
from pathlib import Path

from ipybox import ExecutionClient, ExecutionContainer, arun


@dataclass
class Workspace:
    path: Path

    @property
    def private_skills_path(self) -> Path:
        return self.path / "skills" / "private"

    @property
    def shared_skills_path(self) -> Path:
        return self.path / "skills" / "shared"


class CodeActContainer(ExecutionContainer):
    def __init__(
        self,
        tag: str,
        env: dict[str, str] | None = None,
        workspace_path: Path | None = None,
    ):
        self.workspace = Workspace(workspace_path or Path("workspace"))

        binds = {
            self.workspace.private_skills_path: "skills/private",
            self.workspace.shared_skills_path: "skills/shared",
        }

        # assumed to only exist in development mode i.e. if cwd() is project root
        _builtin_skills_host_path = Path.cwd() / "freeact" / "skills"

        if _builtin_skills_host_path.exists():
            binds[_builtin_skills_host_path] = "skills/builtin/freeact/skills"

        super().__init__(tag=tag, binds=binds, env=env)


class CodeActExecutor(ExecutionClient):
    def __init__(self, key: str, workspace: Workspace, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.key = key
        self.workspace = workspace

        # Host mapping for working directory inside container
        self.workdir = workspace.private_skills_path / key

    async def __aenter__(self):
        await super().__aenter__()
        await arun(self.workdir.mkdir, parents=True, exist_ok=True)
        await self.execute(f"""
            %load_ext autoreload
            %autoreload 2

            workdir = "/home/appuser/skills/private/{self.key}"

            import sys
            sys.path.extend(
                [
                    "/home/appuser/skills/builtin",
                    "/home/appuser/skills/shared",
                    workdir,
                ]
            )

            import os
            os.makedirs(workdir, exist_ok=True)
            os.chdir(workdir)

            from freeact.skills.editor import file_editor
            """)
        return self
