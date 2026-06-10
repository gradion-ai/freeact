from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from pydantic_ai.embeddings import TestEmbeddingModel

from freeact.tools.pytools.search.hybrid.database import Database
from freeact.tools.pytools.search.hybrid.embed import ToolEmbedder


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def dimensions() -> int:
    return 8


@pytest_asyncio.fixture
async def db(db_path: Path, dimensions: int) -> AsyncIterator[Database]:
    async with Database(db_path, dimensions) as db:
        yield db


@pytest.fixture
def embedder(dimensions: int) -> ToolEmbedder:
    return ToolEmbedder(TestEmbeddingModel(dimensions=dimensions))


@pytest.fixture
def fixtures_dir() -> Path:
    tests_root = Path(__file__).parents[5]
    return tests_root / "unit" / "tools" / "pytools" / "search" / "hybrid" / "fixtures"
