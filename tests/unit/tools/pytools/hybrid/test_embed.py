import pytest
from pydantic_ai.embeddings import TestEmbeddingModel

from freeact.tools.pytools.hybrid.embed import ToolEmbedder


@pytest.fixture
def test_model() -> TestEmbeddingModel:
    return TestEmbeddingModel(dimensions=8)


@pytest.fixture
def embedder(test_model: TestEmbeddingModel) -> ToolEmbedder:
    return ToolEmbedder(test_model)


class TestToolEmbedder:
    @pytest.mark.asyncio
    async def test_embed_query_returns_vector(self, embedder: ToolEmbedder) -> None:
        result = await embedder.embed_query("search for GitHub tools")

        assert isinstance(result, list)
        assert len(result) == 8
        assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_embed_query_uses_query_input_type(
        self, embedder: ToolEmbedder, test_model: TestEmbeddingModel
    ) -> None:
        await embedder.embed_query("test query")

        assert test_model.last_settings is not None

    @pytest.mark.parametrize(
        "texts",
        [[], ["Single document"], ["Create a GitHub issue", "List repository files"]],
    )
    @pytest.mark.asyncio
    async def test_embed_documents_returns_vector_per_text(self, embedder: ToolEmbedder, texts: list[str]) -> None:
        results = await embedder.embed_documents(texts)

        assert isinstance(results, list)
        assert len(results) == len(texts)
        for embedding in results:
            assert isinstance(embedding, list)
            assert len(embedding) == 8

    @pytest.mark.asyncio
    async def test_embedder_respects_dimensions_setting(self) -> None:
        embedder = ToolEmbedder(TestEmbeddingModel(dimensions=16))

        result = await embedder.embed_query("test")

        assert len(result) == 16

    @pytest.mark.asyncio
    async def test_embedder_with_model_string(self) -> None:
        embedder = ToolEmbedder("openai:text-embedding-3-small")

        assert embedder is not None
