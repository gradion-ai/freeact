"""Shared fixtures for hybrid search integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.embeddings import TestEmbeddingModel

from freeact.tools.pytools.search.hybrid.embed import ToolEmbedder

# -----------------------------------------------------------------------------
# Database fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def dimensions() -> int:
    """Embedding dimensions for tests."""
    return 8


# -----------------------------------------------------------------------------
# Embedder fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def embedder(dimensions: int) -> ToolEmbedder:
    """Provide a ToolEmbedder with a test model for deterministic embeddings."""
    return ToolEmbedder(TestEmbeddingModel(dimensions=dimensions))


# -----------------------------------------------------------------------------
# Fixtures directory
# -----------------------------------------------------------------------------


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory (shared with unit tests)."""
    tests_root = Path(__file__).parent.parent.parent.parent.parent.parent
    return tests_root / "unit" / "tools" / "pytools" / "search" / "hybrid" / "fixtures"
