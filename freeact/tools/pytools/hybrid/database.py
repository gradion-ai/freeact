"""SQLite database with FTS5 and sqlite-vec for hybrid search."""

from __future__ import annotations

import asyncio
import sqlite3
import struct
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

import sqlite_vec
from ipybox.utils import arun


@dataclass
class ToolEntry:
    """A tool entry stored in the search database."""

    id: str  # "source:category:tool_name"
    description: str  # docstring
    file_hash: str  # SHA256
    embedding: list[float]


@dataclass
class SearchResult:
    """A search result with ID and relevance score."""

    id: str
    score: float


class Database:
    """Async SQLite database with FTS5 and vector search support.

    Uses two virtual tables:
    - entries_vec: sqlite-vec for vector similarity search
    - entries_fts: FTS5 for BM25 text search (id is indexed for name matching)
    """

    def __init__(self, path: Path | str, dimensions: int) -> None:
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        self._path = str(path_obj)
        self._dimensions = dimensions
        self._write_lock = asyncio.Lock()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Create a connection with sqlite-vec loaded, ensuring cleanup."""
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        try:
            yield conn
        finally:
            conn.close()

    async def initialize(self) -> None:
        """Create tables if they don't exist."""

        def _init() -> None:
            with self._connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS entries_vec USING vec0(
                        id TEXT PRIMARY KEY,
                        embedding float[{self._dimensions}]
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                        id,
                        file_hash UNINDEXED,
                        description
                    )
                    """
                )
                conn.commit()

        await arun(_init)

    async def add(self, entry: ToolEntry) -> None:
        """Add a tool entry to both tables."""

        def _add() -> None:
            with self._connection() as conn:
                embedding_bytes = struct.pack(f"{len(entry.embedding)}f", *entry.embedding)
                conn.execute(
                    "INSERT INTO entries_vec (id, embedding) VALUES (?, ?)",
                    (entry.id, embedding_bytes),
                )
                conn.execute(
                    "INSERT INTO entries_fts (id, file_hash, description) VALUES (?, ?, ?)",
                    (entry.id, entry.file_hash, entry.description),
                )
                conn.commit()

        async with self._write_lock:
            await arun(_add)

    async def add_batch(self, entries: list[ToolEntry]) -> None:
        """Add multiple tool entries in a single transaction."""

        def _add_batch() -> None:
            with self._connection() as conn:
                for entry in entries:
                    embedding_bytes = struct.pack(f"{len(entry.embedding)}f", *entry.embedding)
                    conn.execute(
                        "INSERT INTO entries_vec (id, embedding) VALUES (?, ?)",
                        (entry.id, embedding_bytes),
                    )
                    conn.execute(
                        "INSERT INTO entries_fts (id, file_hash, description) VALUES (?, ?, ?)",
                        (entry.id, entry.file_hash, entry.description),
                    )
                conn.commit()

        async with self._write_lock:
            await arun(_add_batch)

    async def update(self, entry: ToolEntry) -> None:
        """Update an existing tool entry in both tables."""

        def _update() -> None:
            with self._connection() as conn:
                embedding_bytes = struct.pack(f"{len(entry.embedding)}f", *entry.embedding)
                # For vec0 tables, delete and re-insert
                conn.execute("DELETE FROM entries_vec WHERE id = ?", (entry.id,))
                conn.execute(
                    "INSERT INTO entries_vec (id, embedding) VALUES (?, ?)",
                    (entry.id, embedding_bytes),
                )
                # For FTS5 tables, delete and re-insert
                conn.execute("DELETE FROM entries_fts WHERE id = ?", (entry.id,))
                conn.execute(
                    "INSERT INTO entries_fts (id, file_hash, description) VALUES (?, ?, ?)",
                    (entry.id, entry.file_hash, entry.description),
                )
                conn.commit()

        async with self._write_lock:
            await arun(_update)

    async def delete(self, id: str) -> None:
        """Delete a tool entry from both tables."""

        def _delete() -> None:
            with self._connection() as conn:
                conn.execute("DELETE FROM entries_vec WHERE id = ?", (id,))
                conn.execute("DELETE FROM entries_fts WHERE id = ?", (id,))
                conn.commit()

        async with self._write_lock:
            await arun(_delete)

    async def get(self, id: str) -> ToolEntry | None:
        """Get a tool entry by ID."""

        def _get() -> ToolEntry | None:
            with self._connection() as conn:
                vec_row = conn.execute("SELECT embedding FROM entries_vec WHERE id = ?", (id,)).fetchone()
                fts_row = conn.execute("SELECT file_hash, description FROM entries_fts WHERE id = ?", (id,)).fetchone()

                if vec_row is None or fts_row is None:
                    return None

                embedding_bytes = vec_row[0]
                n = len(embedding_bytes) // 4
                embedding = list(struct.unpack(f"{n}f", embedding_bytes))
                return ToolEntry(id=id, description=fts_row[1], file_hash=fts_row[0], embedding=embedding)

        result = await arun(_get)
        return result  # type: ignore[return-value]

    async def get_hash(self, id: str) -> str | None:
        """Get the file hash for a tool entry (for change detection)."""

        def _get_hash() -> str | None:
            with self._connection() as conn:
                row = conn.execute("SELECT file_hash FROM entries_fts WHERE id = ?", (id,)).fetchone()
                return row[0] if row else None

        result = await arun(_get_hash)
        return result  # type: ignore[return-value]

    async def exists(self, id: str) -> bool:
        """Check if a tool entry exists."""

        def _exists() -> bool:
            with self._connection() as conn:
                row = conn.execute("SELECT 1 FROM entries_fts WHERE id = ?", (id,)).fetchone()
                return row is not None

        result = await arun(_exists)
        return result  # type: ignore[return-value]

    async def list_ids(self) -> list[str]:
        """List all tool entry IDs."""

        def _list_ids() -> list[str]:
            with self._connection() as conn:
                rows = conn.execute("SELECT id FROM entries_fts").fetchall()
                return [row[0] for row in rows]

        result = await arun(_list_ids)
        return result  # type: ignore[return-value]

    def _prepare_fts_query(self, query: str) -> str:
        """Convert query to FTS5 OR query for better recall.

        Tokens are quoted to escape FTS5 special characters (commas,
        parentheses, colons, etc.) that would otherwise cause syntax errors.
        """
        tokens = query.split()
        if not tokens:
            return '""'
        # Quote each token to escape special characters (double internal quotes)
        quoted = ['"' + token.replace('"', '""') + '"' for token in tokens]
        if len(quoted) == 1:
            return quoted[0]
        return " OR ".join(quoted)

    async def bm25_search(self, query: str, limit: int) -> list[SearchResult]:
        """Search using BM25 ranking on id and description columns."""

        def _search() -> list[SearchResult]:
            with self._connection() as conn:
                fts_query = self._prepare_fts_query(query)
                rows = conn.execute(
                    """
                    SELECT id, bm25(entries_fts)
                    FROM entries_fts
                    WHERE entries_fts MATCH ?
                    ORDER BY bm25(entries_fts)
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
                # BM25 returns negative scores (lower is better), negate for consistency
                return [SearchResult(id=row[0], score=-row[1]) for row in rows]

        result = await arun(_search)
        return result  # type: ignore[return-value]

    async def vector_search(self, embedding: list[float], limit: int) -> list[SearchResult]:
        """Search using vector similarity."""

        def _search() -> list[SearchResult]:
            with self._connection() as conn:
                embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)
                rows = conn.execute(
                    """
                    SELECT id, distance
                    FROM entries_vec
                    WHERE embedding MATCH ?
                    ORDER BY distance
                    LIMIT ?
                    """,
                    (embedding_bytes, limit),
                ).fetchall()
                # Distance is lower-is-better, convert to higher-is-better score
                return [SearchResult(id=row[0], score=1.0 - row[1]) for row in rows]

        result = await arun(_search)
        return result  # type: ignore[return-value]

    async def __aenter__(self) -> Database:
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass
