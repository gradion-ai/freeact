import asyncio

import pytest

from freeact.tools.pytools.hybrid.database import Database, ToolEntry


@pytest.fixture
def sample_entry() -> ToolEntry:
    return ToolEntry(
        id="mcptools:github:create_issue",
        description="Create a new issue in a GitHub repository.",
        file_hash="abc123",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
    )


@pytest.fixture
def sample_entries() -> list[ToolEntry]:
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


@pytest.mark.asyncio
async def test_add_and_get(db: Database, sample_entry: ToolEntry) -> None:
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
async def test_get_nonexistent(db: Database) -> None:
    assert await db.get("nonexistent:tool:id") is None
    assert await db.get_hash("nonexistent:tool:id") is None


@pytest.mark.asyncio
async def test_add_batch(db: Database, sample_entries: list[ToolEntry]) -> None:
    await db.add_batch(sample_entries)

    for entry in sample_entries:
        result = await db.get(entry.id)
        assert result is not None
        assert result.id == entry.id


@pytest.mark.asyncio
async def test_update(db: Database, sample_entry: ToolEntry) -> None:
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
async def test_delete(db: Database, sample_entry: ToolEntry) -> None:
    await db.add(sample_entry)
    await db.delete(sample_entry.id)

    assert await db.get(sample_entry.id) is None


@pytest.mark.asyncio
async def test_exists(db: Database, sample_entry: ToolEntry) -> None:
    assert await db.exists(sample_entry.id) is False
    await db.add(sample_entry)
    assert await db.exists(sample_entry.id) is True


@pytest.mark.asyncio
async def test_get_hash(db: Database, sample_entry: ToolEntry) -> None:
    await db.add(sample_entry)

    assert await db.get_hash(sample_entry.id) == sample_entry.file_hash


@pytest.mark.asyncio
async def test_list_ids(db: Database, sample_entries: list[ToolEntry]) -> None:
    assert await db.list_ids() == []

    await db.add_batch(sample_entries)
    ids = await db.list_ids()

    assert set(ids) == {e.id for e in sample_entries}


@pytest.mark.asyncio
async def test_concurrent_reads(db: Database, sample_entries: list[ToolEntry]) -> None:
    await db.add_batch(sample_entries)

    results = await asyncio.gather(*[db.get(entry.id) for entry in sample_entries])

    assert len(results) == len(sample_entries)
    for result in results:
        assert result is not None


@pytest.mark.asyncio
async def test_write_lock_serializes_writes(db: Database, sample_entries: list[ToolEntry]) -> None:
    await asyncio.gather(*[db.add(entry) for entry in sample_entries])

    ids = await db.list_ids()

    assert set(ids) == {e.id for e in sample_entries}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_ids"),
    [
        ("GitHub repository", {"mcptools:github:create_issue", "mcptools:github:list_issues"}),
        ("csv", {"gentools:data:csv_parser"}),
    ],
)
async def test_bm25_matches(db: Database, sample_entries: list[ToolEntry], query: str, expected_ids: set[str]) -> None:
    await db.add_batch(sample_entries)
    results = await db.bm25_search(query, limit=10)

    assert expected_ids <= {r.id for r in results}


@pytest.mark.asyncio
async def test_bm25_no_match(db: Database, sample_entries: list[ToolEntry]) -> None:
    await db.add_batch(sample_entries)

    assert await db.bm25_search("nonexistent", limit=10) == []


@pytest.mark.asyncio
async def test_bm25_respects_limit(db: Database, sample_entries: list[ToolEntry]) -> None:
    await db.add_batch(sample_entries)
    results = await db.bm25_search("issue data parse", limit=2)

    assert len(results) <= 2


@pytest.mark.asyncio
async def test_vector_search_nearest(db: Database, sample_entries: list[ToolEntry]) -> None:
    await db.add_batch(sample_entries)
    results = await db.vector_search([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], limit=3)

    assert len(results) > 0
    assert results[0].id == "mcptools:github:create_issue"


@pytest.mark.asyncio
async def test_vector_search_respects_limit(db: Database, sample_entries: list[ToolEntry]) -> None:
    await db.add_batch(sample_entries)
    results = await db.vector_search([0.5] * 8, limit=2)

    assert len(results) <= 2


@pytest.mark.asyncio
async def test_vector_search_scores_descending(db: Database, sample_entries: list[ToolEntry]) -> None:
    await db.add_batch(sample_entries)
    results = await db.vector_search([0.5] * 8, limit=10)

    for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score
