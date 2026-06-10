import pytest
import pytest_asyncio

from freeact.tools.pytools.hybrid.database import Database, ToolEntry
from freeact.tools.pytools.hybrid.search import SearchConfig, SearchEngine


@pytest.fixture
def sample_entries() -> list[ToolEntry]:
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


@pytest_asyncio.fixture
async def engine(db: Database, sample_entries: list[ToolEntry]) -> SearchEngine:
    await db.add_batch(sample_entries)
    return SearchEngine(db)


@pytest.mark.asyncio
async def test_bm25_finds_matching_documents(engine: SearchEngine) -> None:
    results = await engine.bm25_search("GitHub", limit=10)

    ids = [r.id for r in results]
    assert "mcptools:github:create_issue" in ids
    assert "mcptools:github:list_issues" in ids


@pytest.mark.asyncio
async def test_bm25_returns_empty_for_no_matches(engine: SearchEngine) -> None:
    assert await engine.bm25_search("nonexistent", limit=10) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "GitHub, issues",
        "issue (create)",
        "issue:github",
        'issue "quoted"',
        "issue -negation",
        "issue* prefix",
        "(grouped) terms",
    ],
)
async def test_bm25_handles_special_characters(engine: SearchEngine, query: str) -> None:
    results = await engine.bm25_search(query, limit=10)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_vector_finds_similar(engine: SearchEngine) -> None:
    results = await engine.vector_search([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], limit=2)

    ids = [r.id for r in results]
    assert "mcptools:github:create_issue" in ids
    assert "mcptools:github:list_issues" in ids


@pytest.mark.asyncio
async def test_vector_order_by_similarity(engine: SearchEngine) -> None:
    results = await engine.vector_search([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], limit=4)

    assert results[0].id == "gentools:data:csv_parser"


@pytest.mark.asyncio
async def test_hybrid_combines_results(engine: SearchEngine) -> None:
    results = await engine.hybrid_search("issue", [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], limit=10)

    ids = [r.id for r in results]
    assert "mcptools:github:create_issue" in ids
    assert "mcptools:github:list_issues" in ids


@pytest.mark.asyncio
async def test_rrf_boosts_documents_in_both_lists(engine: SearchEngine) -> None:
    results = await engine.hybrid_search("issue", [0.95, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], limit=4)

    issue_tools = [r for r in results if "issue" in r.id]
    assert len(issue_tools) >= 2
    assert "issue" in results[0].id


@pytest.mark.asyncio
async def test_weights_affect_ranking(db: Database) -> None:
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
    await db.add_batch(entries)

    query = "keyword"
    query_embedding = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    engine_bm25 = SearchEngine(db, SearchConfig(bm25_weight=10.0, vec_weight=0.1))
    results_bm25 = await engine_bm25.hybrid_search(query, query_embedding, limit=2)

    engine_vec = SearchEngine(db, SearchConfig(bm25_weight=0.1, vec_weight=10.0))
    results_vec = await engine_vec.hybrid_search(query, query_embedding, limit=2)

    assert results_bm25[0].id == "tool:a:bm25_match"
    assert results_vec[0].id == "tool:b:vec_match"


@pytest.mark.asyncio
async def test_limit_respected(engine: SearchEngine) -> None:
    results = await engine.hybrid_search("issue data message", [0.5, 0.1, 0.1, 0.1, 0.0, 0.0, 0.1, 0.1], limit=2)

    assert len(results) <= 2


@pytest.mark.asyncio
async def test_empty_database(db: Database, dimensions: int) -> None:
    engine = SearchEngine(db)

    assert await engine.hybrid_search("query", [0.0] * dimensions, limit=10) == []


def test_default_config() -> None:
    config = SearchConfig()

    assert config.bm25_weight == 1.0
    assert config.vec_weight == 1.0
    assert config.rrf_k == 60
    assert config.overfetch_multiplier == 2


def test_custom_config() -> None:
    config = SearchConfig(bm25_weight=2.0, vec_weight=0.5, rrf_k=30, overfetch_multiplier=3)

    assert config.bm25_weight == 2.0
    assert config.vec_weight == 0.5
    assert config.rrf_k == 30
    assert config.overfetch_multiplier == 3
