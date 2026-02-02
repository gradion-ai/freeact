"""Embedder integration for generating tool embeddings."""

from __future__ import annotations

from pydantic_ai.embeddings import (
    Embedder,
    EmbeddingModel,
    EmbeddingSettings,
    KnownEmbeddingModelName,
)


class ToolEmbedder:
    """Generates embeddings for tool descriptions and search queries.

    Wraps pydantic-ai's Embedder to provide asymmetric embedding support,
    where queries and documents are embedded differently for optimal retrieval.

    Args:
        model: The embedding model to use. Can be:
            - A model name string in the format 'provider:model-name'
              (e.g., 'google-gla:gemini-embedding-001')
            - An EmbeddingModel instance
        settings: Optional embedding settings (e.g., dimensions).

    Example:
        ```python
        embedder = ToolEmbedder(
            "google-gla:gemini-embedding-001",
            {"dimensions": 768},
        )
        query_embedding = await embedder.embed_query("search tools for GitHub")
        doc_embeddings = await embedder.embed_documents(["Create GitHub issue", "List repos"])
        ```
    """

    def __init__(
        self,
        model: EmbeddingModel | KnownEmbeddingModelName | str,
        settings: EmbeddingSettings | None = None,
    ) -> None:
        self._embedder = Embedder(model, settings=settings)

    async def embed_query(self, text: str) -> list[float]:
        """Generate an embedding for a search query.

        Uses the asymmetric 'query' input type, which some models optimize
        differently from document embeddings.

        Args:
            text: The query text to embed.

        Returns:
            The embedding vector as a list of floats.
        """
        result = await self._embedder.embed_query(text)
        return list(result.embeddings[0])

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for documents (tool descriptions).

        Uses the asymmetric 'document' input type, which some models optimize
        differently from query embeddings.

        Args:
            texts: List of document texts to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []
        result = await self._embedder.embed_documents(texts)
        return [list(emb) for emb in result.embeddings]
