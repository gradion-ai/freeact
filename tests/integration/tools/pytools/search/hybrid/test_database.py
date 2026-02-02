"""Unit tests for the hybrid search database module."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from freeact.agent.tools.pytools.search.hybrid.database import Database, ToolEntry


@pytest.fixture
def sample_entry() -> ToolEntry:
    """Provide a sample tool entry."""
    return ToolEntry(
        id="mcptools:github:create_issue",
        description="Create a new issue in a GitHub repository.",
        file_hash="abc123",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
    )


@pytest.fixture
def sample_entries() -> list[ToolEntry]:
    """Provide multiple sample tool entries."""
    return [
        ToolEntry(
            id="mcptools:github:create_issue",
            description="Create a new issue in a GitHub repository.",
            file_hash="hash1",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        ),
        ToolEntry(
            id="mcptools:github:list_issues",
            description="List issues in a GitHub repository.",
            file_hash="hash2",
            embedding=[0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
        ),
        ToolEntry(
            id="gentools:data:csv_parser",
            description="Parse CSV files into structured data.",
            file_hash="hash3",
            embedding=[0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2],
        ),
    ]


class TestDatabaseCRUD:
    """Tests for CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_and_get(self, db_path: Path, dimensions: int, sample_entry: ToolEntry) -> None:
        """Test adding and retrieving a tool entry."""
        async with Database(db_path, dimensions) as db:
            await db.add(sample_entry)
            result = await db.get(sample_entry.id)

        assert result is not None
        assert result.id == sample_entry.id
        assert result.description == sample_entry.description
        assert result.file_hash == sample_entry.file_hash
        assert len(result.embedding) == len(sample_entry.embedding)
        for a, b in zip(result.embedding, sample_entry.embedding, strict=True):
            assert abs(a - b) < 1e-6

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db_path: Path, dimensions: int) -> None:
        """Test getting a nonexistent entry returns None."""
        async with Database(db_path, dimensions) as db:
            result = await db.get("nonexistent:tool:id")

        assert result is None

    @pytest.mark.asyncio
    async def test_add_batch(self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]) -> None:
        """Test batch adding multiple entries."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)

            for entry in sample_entries:
                result = await db.get(entry.id)
                assert result is not None
                assert result.id == entry.id

    @pytest.mark.asyncio
    async def test_update(self, db_path: Path, dimensions: int, sample_entry: ToolEntry) -> None:
        """Test updating an existing entry."""
        async with Database(db_path, dimensions) as db:
            await db.add(sample_entry)

            updated_entry = ToolEntry(
                id=sample_entry.id,
                description="Updated description.",
                file_hash="newhash",
                embedding=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            )
            await db.update(updated_entry)

            result = await db.get(sample_entry.id)

        assert result is not None
        assert result.description == "Updated description."
        assert result.file_hash == "newhash"

    @pytest.mark.asyncio
    async def test_delete(self, db_path: Path, dimensions: int, sample_entry: ToolEntry) -> None:
        """Test deleting an entry."""
        async with Database(db_path, dimensions) as db:
            await db.add(sample_entry)
            await db.delete(sample_entry.id)
            result = await db.get(sample_entry.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_exists(self, db_path: Path, dimensions: int, sample_entry: ToolEntry) -> None:
        """Test checking if an entry exists."""
        async with Database(db_path, dimensions) as db:
            assert await db.exists(sample_entry.id) is False
            await db.add(sample_entry)
            assert await db.exists(sample_entry.id) is True


class TestHashOperations:
    """Tests for hash-based change detection."""

    @pytest.mark.asyncio
    async def test_get_hash(self, db_path: Path, dimensions: int, sample_entry: ToolEntry) -> None:
        """Test getting a file hash."""
        async with Database(db_path, dimensions) as db:
            await db.add(sample_entry)
            result = await db.get_hash(sample_entry.id)

        assert result == sample_entry.file_hash

    @pytest.mark.asyncio
    async def test_get_hash_nonexistent(self, db_path: Path, dimensions: int) -> None:
        """Test getting hash for nonexistent entry."""
        async with Database(db_path, dimensions) as db:
            result = await db.get_hash("nonexistent:tool:id")

        assert result is None


class TestListOperations:
    """Tests for listing operations."""

    @pytest.mark.asyncio
    async def test_list_ids(self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]) -> None:
        """Test listing all IDs."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            ids = await db.list_ids()

        assert set(ids) == {e.id for e in sample_entries}

    @pytest.mark.asyncio
    async def test_list_ids_empty(self, db_path: Path, dimensions: int) -> None:
        """Test listing IDs from empty database."""
        async with Database(db_path, dimensions) as db:
            ids = await db.list_ids()

        assert ids == []


class TestConcurrency:
    """Tests for concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]) -> None:
        """Test concurrent reads succeed."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)

            # Run multiple concurrent reads
            results = await asyncio.gather(*[db.get(entry.id) for entry in sample_entries])

        assert len(results) == len(sample_entries)
        for result in results:
            assert result is not None

    @pytest.mark.asyncio
    async def test_write_lock_serializes_writes(
        self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]
    ) -> None:
        """Test that writes are serialized by the lock."""
        async with Database(db_path, dimensions) as db:
            # Run multiple concurrent writes
            await asyncio.gather(*[db.add(entry) for entry in sample_entries])

            # All should have been added
            ids = await db.list_ids()

        assert set(ids) == {e.id for e in sample_entries}


class TestBM25Search:
    """Tests for BM25 text search."""

    @pytest.mark.asyncio
    async def test_bm25_matches_description(
        self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]
    ) -> None:
        """Test BM25 search matches on description content."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            results = await db.bm25_search("GitHub repository", limit=10)

        # Both GitHub tools should match
        ids = [r.id for r in results]
        assert "mcptools:github:create_issue" in ids
        assert "mcptools:github:list_issues" in ids

    @pytest.mark.asyncio
    async def test_bm25_matches_id_tokens(
        self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]
    ) -> None:
        """Test BM25 search matches on id tokens (tool name, category)."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            results = await db.bm25_search("csv", limit=10)

        ids = [r.id for r in results]
        assert "gentools:data:csv_parser" in ids

    @pytest.mark.asyncio
    async def test_bm25_no_match(self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]) -> None:
        """Test BM25 search returns empty for no matches."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            results = await db.bm25_search("nonexistent", limit=10)

        assert results == []

    @pytest.mark.asyncio
    async def test_bm25_respects_limit(self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]) -> None:
        """Test BM25 search respects limit parameter."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            # Query that should match all entries (issue, data, parse are split and joined with OR)
            results = await db.bm25_search("issue data parse", limit=2)

        assert len(results) <= 2


class TestVectorSearch:
    """Tests for vector similarity search."""

    @pytest.mark.asyncio
    async def test_vector_search_nearest(self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]) -> None:
        """Test vector search returns nearest neighbors."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)

            # Query with embedding similar to first entry
            query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
            results = await db.vector_search(query_embedding, limit=3)

        # First result should be the most similar
        assert len(results) > 0
        assert results[0].id == "mcptools:github:create_issue"

    @pytest.mark.asyncio
    async def test_vector_search_respects_limit(
        self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]
    ) -> None:
        """Test vector search respects limit parameter."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)

            query_embedding = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
            results = await db.vector_search(query_embedding, limit=2)

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_vector_search_scores(self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]) -> None:
        """Test vector search returns scores in descending order."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)

            query_embedding = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
            results = await db.vector_search(query_embedding, limit=10)

        # Scores should be in descending order
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score


class TestContextManager:
    """Tests for context manager behavior."""

    @pytest.mark.asyncio
    async def test_context_manager_initializes_tables(self, db_path: Path, dimensions: int) -> None:
        """Test context manager creates tables on entry."""
        async with Database(db_path, dimensions) as db:
            # Should not raise - tables exist
            await db.add(
                ToolEntry(
                    id="test:cat:tool",
                    description="Test",
                    file_hash="hash",
                    embedding=[0.0] * dimensions,
                )
            )
