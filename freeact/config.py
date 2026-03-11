import json
from pathlib import Path
from typing import Any, ClassVar, Self

from ipybox.utils import arun
from pydantic import BaseModel, ConfigDict, Field

FREEACT_DIR_NAME = ".freeact"


class PersistentConfig(BaseModel):
    """Base class for JSON-persisted configuration models.

    Subclasses set `_config_filename` to their JSON filename and
    override `model_post_init` / `_save_sync` for domain-specific logic.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, frozen=True)
    _config_filename: ClassVar[str]
    working_dir: Path = Field(default_factory=Path.cwd, exclude=True)

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "working_dir", self.working_dir.resolve())

    @property
    def freeact_dir(self) -> Path:
        return self.working_dir / FREEACT_DIR_NAME

    @property
    def _config_file(self) -> Path:
        return self.freeact_dir / self._config_filename

    async def save(self) -> None:
        """Persist config to the `.freeact/` directory."""
        await arun(self._save_sync)

    @classmethod
    async def load(cls, working_dir: Path | None = None) -> Self:
        """Load persisted config if present, otherwise return defaults."""
        config = cls(working_dir=working_dir or Path.cwd())
        config_file = config._config_file
        if not config_file.exists():
            return config

        data = await arun(lambda: json.loads(config_file.read_text()))
        return cls.model_validate(
            {
                **data,
                "working_dir": config.working_dir,
            }
        )

    @classmethod
    async def init(cls, working_dir: Path | None = None) -> Self:
        """Load config when present, otherwise save defaults."""
        config = cls(working_dir=working_dir or Path.cwd())
        if config._config_file.exists():
            return await cls.load(working_dir=config.working_dir)

        await config.save()
        return config

    def _save_sync(self) -> None:
        self.freeact_dir.mkdir(parents=True, exist_ok=True)
        payload = self.model_dump(mode="json", exclude={"working_dir"})
        self._config_file.write_text(json.dumps(payload, indent=2) + "\n")
