"""Search engine with BM25, vector, and hybrid search modes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from freeact.tools.pytools.search.hybrid.database import Database, SearchResult


@dataclass
class SearchConfig:
    """Configuration for hybrid search."""

    bm25_weight: float = 1.0
    vec_weight: float = 1.0
    rrf_k: int = 60
    overfetch_multiplier: int = 2


class SearchEngine:
    """Search engine supporting BM25, vector, and hybrid search modes.

    Hybrid search uses Reciprocal Rank Fusion (RRF) to combine results
    from both BM25 and vector search.
    """

    def __init__(self, database: Database, config: SearchConfig | None = None) -> None:
        self._database = database
        self._config = config or SearchConfig()

    async def bm25_search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search using BM25 text matching.

        Args:
            query: Search query string.
            limit: Maximum number of results to return.

        Returns:
            List of search results sorted by relevance.
        """
        return await self._database.bm25_search(query, limit)

    async def vector_search(self, embedding: list[float], limit: int = 10) -> list[SearchResult]:
        """Search using vector similarity.

        Args:
            embedding: Query embedding vector.
            limit: Maximum number of results to return.

        Returns:
            List of search results sorted by similarity.
        """
        return await self._database.vector_search(embedding, limit)

    def _reciprocal_rank_fusion(
        self,
        bm25_results: list[SearchResult],
        vec_results: list[SearchResult],
    ) -> list[SearchResult]:
        """Combine results using Reciprocal Rank Fusion.

        RRF formula: score += weight / (k + rank + 1)
        """
        scores: dict[str, float] = {}
        k = self._config.rrf_k

        for rank, result in enumerate(bm25_results):
            scores.setdefault(result.id, 0.0)
            scores[result.id] += self._config.bm25_weight / (k + rank + 1)

        for rank, result in enumerate(vec_results):
            scores.setdefault(result.id, 0.0)
            scores[result.id] += self._config.vec_weight / (k + rank + 1)

        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [SearchResult(id=id, score=score) for id, score in sorted_items]

    async def hybrid_search(
        self,
        query: str,
        embedding: list[float],
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search using both BM25 and vector similarity with RRF fusion.

        Args:
            query: Search query string for BM25.
            embedding: Query embedding vector for vector search.
            limit: Maximum number of results to return.

        Returns:
            List of search results sorted by combined relevance.
        """
        fetch_limit = limit * self._config.overfetch_multiplier

        bm25_results, vec_results = await asyncio.gather(
            self._database.bm25_search(query, fetch_limit),
            self._database.vector_search(embedding, fetch_limit),
        )

        fused = self._reciprocal_rank_fusion(bm25_results, vec_results)
        return fused[:limit]
