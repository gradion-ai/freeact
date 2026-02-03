"""Unit tests for the search engine module."""

from __future__ import annotations

from pathlib import Path

import pytest

from freeact.agent.tools.pytools.search.hybrid.database import Database, ToolEntry
from freeact.agent.tools.pytools.search.hybrid.search import SearchConfig, SearchEngine


@pytest.fixture
def sample_entries() -> list[ToolEntry]:
    """Provide sample tool entries for search tests."""
    return [
        ToolEntry(
            id="mcptools:github:create_issue",
            description="Create a new issue in a GitHub repository.",
            file_hash="hash1",
            embedding=[0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # distinct direction
        ),
        ToolEntry(
            id="mcptools:github:list_issues",
            description="List issues in a GitHub repository.",
            file_hash="hash2",
            embedding=[0.8, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # similar to first
        ),
        ToolEntry(
            id="gentools:data:csv_parser",
            description="Parse CSV files into structured data.",
            file_hash="hash3",
            embedding=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.9],  # orthogonal to first
        ),
        ToolEntry(
            id="mcptools:slack:send_message",
            description="Send a message to a Slack channel.",
            file_hash="hash4",
            embedding=[0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0],  # also orthogonal
        ),
    ]


class TestBM25Search:
    """Tests for BM25 search."""

    @pytest.mark.asyncio
    async def test_bm25_finds_matching_documents(
        self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]
    ) -> None:
        """Test BM25 search finds documents matching query terms."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            engine = SearchEngine(db)

            results = await engine.bm25_search("GitHub", limit=10)

        ids = [r.id for r in results]
        assert "mcptools:github:create_issue" in ids
        assert "mcptools:github:list_issues" in ids

    @pytest.mark.asyncio
    async def test_bm25_returns_empty_for_no_matches(
        self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]
    ) -> None:
        """Test BM25 search returns empty list for no matches."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            engine = SearchEngine(db)

            results = await engine.bm25_search("nonexistent", limit=10)

        assert results == []


class TestVectorSearch:
    """Tests for vector similarity search."""

    @pytest.mark.asyncio
    async def test_vector_finds_similar(self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]) -> None:
        """Test vector search finds similar embeddings."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            engine = SearchEngine(db)

            # Query similar to first two entries
            query_embedding = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            results = await engine.vector_search(query_embedding, limit=2)

        ids = [r.id for r in results]
        assert "mcptools:github:create_issue" in ids
        assert "mcptools:github:list_issues" in ids

    @pytest.mark.asyncio
    async def test_vector_order_by_similarity(
        self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]
    ) -> None:
        """Test vector search orders results by similarity."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            engine = SearchEngine(db)

            # Query embedding close to csv_parser
            query_embedding = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
            results = await engine.vector_search(query_embedding, limit=4)

        # csv_parser should be most similar
        assert results[0].id == "gentools:data:csv_parser"


class TestHybridSearch:
    """Tests for hybrid search with RRF fusion."""

    @pytest.mark.asyncio
    async def test_hybrid_combines_results(
        self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]
    ) -> None:
        """Test hybrid search combines BM25 and vector results."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            engine = SearchEngine(db)

            # Query that matches "issue" via BM25 and similar embedding
            query = "issue"
            query_embedding = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            results = await engine.hybrid_search(query, query_embedding, limit=10)

        ids = [r.id for r in results]
        # Both issue tools should be in results
        assert "mcptools:github:create_issue" in ids
        assert "mcptools:github:list_issues" in ids

    @pytest.mark.asyncio
    async def test_rrf_boosts_documents_in_both_lists(
        self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]
    ) -> None:
        """Test RRF gives higher scores to documents appearing in both result sets."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            engine = SearchEngine(db)

            # Query: "issue" matches BM25, embedding similar to create_issue
            query = "issue"
            query_embedding = [0.95, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            results = await engine.hybrid_search(query, query_embedding, limit=4)

        # create_issue should rank higher due to appearing in both result sets
        # with good positions in each
        issue_tools = [r for r in results if "issue" in r.id]
        assert len(issue_tools) >= 2

        # The first result should be one of the issue tools
        assert "issue" in results[0].id

    @pytest.mark.asyncio
    async def test_weights_affect_ranking(self, db_path: Path, dimensions: int) -> None:
        """Test that bm25_weight and vec_weight affect final ranking."""
        entries = [
            ToolEntry(
                id="tool:a:bm25_match",
                description="keyword specific unique term",
                file_hash="h1",
                embedding=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1],  # not similar
            ),
            ToolEntry(
                id="tool:b:vec_match",
                description="unrelated description here",
                file_hash="h2",
                embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # very similar
            ),
        ]

        async with Database(db_path, dimensions) as db:
            await db.add_batch(entries)

            # High BM25 weight, low vector weight
            config_bm25 = SearchConfig(bm25_weight=10.0, vec_weight=0.1)
            engine_bm25 = SearchEngine(db, config_bm25)

            query = "keyword"
            query_embedding = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            results_bm25 = await engine_bm25.hybrid_search(query, query_embedding, limit=2)

            # High vector weight, low BM25 weight
            config_vec = SearchConfig(bm25_weight=0.1, vec_weight=10.0)
            engine_vec = SearchEngine(db, config_vec)
            results_vec = await engine_vec.hybrid_search(query, query_embedding, limit=2)

        # With high BM25 weight, bm25_match should rank first
        assert results_bm25[0].id == "tool:a:bm25_match"

        # With high vector weight, vec_match should rank first
        assert results_vec[0].id == "tool:b:vec_match"

    @pytest.mark.asyncio
    async def test_limit_respected(self, db_path: Path, dimensions: int, sample_entries: list[ToolEntry]) -> None:
        """Test hybrid search respects limit parameter."""
        async with Database(db_path, dimensions) as db:
            await db.add_batch(sample_entries)
            engine = SearchEngine(db)

            query = "issue data message"
            query_embedding = [0.5, 0.1, 0.1, 0.1, 0.0, 0.0, 0.1, 0.1]
            results = await engine.hybrid_search(query, query_embedding, limit=2)

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_empty_inputs(self, db_path: Path, dimensions: int) -> None:
        """Test hybrid search handles empty database."""
        async with Database(db_path, dimensions) as db:
            engine = SearchEngine(db)

            results = await engine.hybrid_search("query", [0.0] * dimensions, limit=10)

        assert results == []


class TestSearchConfig:
    """Tests for SearchConfig defaults and customization."""

    def test_default_config(self) -> None:
        """Test SearchConfig has sensible defaults."""
        config = SearchConfig()

        assert config.bm25_weight == 1.0
        assert config.vec_weight == 1.0
        assert config.rrf_k == 60
        assert config.overfetch_multiplier == 2

    def test_custom_config(self) -> None:
        """Test SearchConfig accepts custom values."""
        config = SearchConfig(
            bm25_weight=2.0,
            vec_weight=0.5,
            rrf_k=30,
            overfetch_multiplier=3,
        )

        assert config.bm25_weight == 2.0
        assert config.vec_weight == 0.5
        assert config.rrf_k == 30
        assert config.overfetch_multiplier == 3
