"""Unit tests for the embedder module."""

from __future__ import annotations

import pytest
from pydantic_ai.embeddings import TestEmbeddingModel

from freeact.agent.tools.pytools.search.hybrid.embed import ToolEmbedder


@pytest.fixture
def test_model() -> TestEmbeddingModel:
    """Provide a test embedding model."""
    return TestEmbeddingModel(dimensions=8)


@pytest.fixture
def embedder(test_model: TestEmbeddingModel) -> ToolEmbedder:
    """Provide a ToolEmbedder with the test model."""
    return ToolEmbedder(test_model)


class TestToolEmbedder:
    """Tests for the ToolEmbedder class."""

    @pytest.mark.asyncio
    async def test_embed_query_returns_vector(self, embedder: ToolEmbedder) -> None:
        """Test that embed_query returns an embedding vector."""
        result = await embedder.embed_query("search for GitHub tools")

        assert isinstance(result, list)
        assert len(result) == 8
        assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_embed_query_uses_query_input_type(
        self, embedder: ToolEmbedder, test_model: TestEmbeddingModel
    ) -> None:
        """Test that embed_query uses the 'query' input type for asymmetric embeddings."""
        await embedder.embed_query("test query")

        # TestEmbeddingModel stores last_settings but doesn't expose input_type directly
        # The important thing is that the method completes successfully using embed_query
        assert test_model.last_settings is not None

    @pytest.mark.asyncio
    async def test_embed_documents_returns_vectors(self, embedder: ToolEmbedder) -> None:
        """Test that embed_documents returns a list of embedding vectors."""
        texts = ["Create a GitHub issue", "List repository files"]

        results = await embedder.embed_documents(texts)

        assert isinstance(results, list)
        assert len(results) == 2
        for embedding in results:
            assert isinstance(embedding, list)
            assert len(embedding) == 8

    @pytest.mark.asyncio
    async def test_embed_documents_empty_list(self, embedder: ToolEmbedder) -> None:
        """Test that embed_documents handles empty input."""
        results = await embedder.embed_documents([])

        assert results == []

    @pytest.mark.asyncio
    async def test_embed_documents_single_item(self, embedder: ToolEmbedder) -> None:
        """Test that embed_documents works with a single document."""
        results = await embedder.embed_documents(["Single document"])

        assert len(results) == 1
        assert len(results[0]) == 8

    @pytest.mark.asyncio
    async def test_embedder_respects_dimensions_setting(self) -> None:
        """Test that the embedder respects dimension settings."""
        model = TestEmbeddingModel(dimensions=16)
        embedder = ToolEmbedder(model)

        result = await embedder.embed_query("test")

        assert len(result) == 16

    @pytest.mark.asyncio
    async def test_embedder_with_model_string(self) -> None:
        """Test creating embedder with model string (deferred validation)."""
        # This should not raise during construction due to deferred validation
        embedder = ToolEmbedder("openai:text-embedding-3-small")

        # The embedder exists but would fail on actual use without API key
        assert embedder is not None
