import json
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import patch

import pytest
import requests

from freeact.skills.reader.api import Document, create_readwise_reader


@pytest.fixture
def mock_save_response():
    return {
        "id": "01gwfvp9pyaabcdgmx14f6ha0",
        "url": "https://readwise.io/new/read/01gwfvp9pyaabcdgmx14f6ha0",
    }


@pytest.fixture
def mock_list_response():
    return {
        "count": 2,
        "nextPageCursor": None,
        "results": [
            {
                "id": "01gwfvp9pyaabcdgmx14f6ha0",
                "url": "https://readwise.io/feed/read/01gwfvp9pyaabcdgmx14f6ha0",
                "source_url": "https://example.com/article1",
                "title": "Test Article 1",
                "author": "Test Author",
                "source": "Reader RSS",
                "category": "article",
                "location": "new",
                "tags": {"test": {}},
                "notes": "Test note",
                "site_name": "Example",
                "word_count": 100,
                "summary": "Test summary",
                "reading_progress": 0.5,
                "created_at": "2024-03-20T10:00:00Z",
                "updated_at": "2024-03-20T10:00:00Z",
                "saved_at": "2024-03-20T10:00:00Z",
                "last_moved_at": "2024-03-20T10:00:00Z",
                "first_opened_at": "2024-03-20T10:00:00Z",
                "last_opened_at": "2024-03-20T10:00:00Z",
                "published_date": "2024-03-20",
                "image_url": "https://example.com/image.jpg",
                "parent_id": None,
            }
        ],
    }


class MockResponse:
    def __init__(self, json_data: Dict[str, Any], status_code: int = 200):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP Error: {self.status_code}")


def test_create_readwise_reader():
    with patch.dict("os.environ", {"READWISE_API_KEY": "test-key"}):
        reader = create_readwise_reader()
        assert reader is not None
        assert reader.api_key == "test-key"  # type: ignore


def test_create_readwise_reader_with_key():
    reader = create_readwise_reader(api_key="test-key")
    assert reader is not None
    assert reader.api_key == "test-key"  # type: ignore


@patch("requests.post")
def test_save_document_url(mock_post, mock_save_response):
    mock_post.return_value = MockResponse(mock_save_response)

    reader = create_readwise_reader("test-key")
    reader.save_document_url(
        url="https://example.com/article",
        location="new",
        category="article",
        tags=["test"],
        note="Test note",
    )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"] == {"Authorization": "Token test-key"}
    assert call_kwargs["url"] == "https://readwise.io/api/v3/save/"

    body = json.loads(json.dumps(call_kwargs["json"]))
    assert body["url"] == "https://example.com/article"
    assert body["location"] == "new"
    assert body["category"] == "article"
    assert body["tags"] == ["test"]
    assert body["notes"] == "Test note"


@patch("requests.post")
def test_save_document_html(mock_post, mock_save_response):
    mock_post.return_value = MockResponse(mock_save_response)

    reader = create_readwise_reader("test-key")
    reader.save_document_html(
        html="<h1>Test</h1>",
        title="Test Document",
        location="new",
        category="article",
        tags=["test"],
        note="Test note",
    )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"] == {"Authorization": "Token test-key"}
    assert call_kwargs["url"] == "https://readwise.io/api/v3/save/"

    body = json.loads(json.dumps(call_kwargs["json"]))
    assert body["html"] == "<h1>Test</h1>"
    assert body["title"] == "Test Document"
    assert body["should_clean_html"] is True
    assert body["location"] == "new"
    assert body["category"] == "article"
    assert body["tags"] == ["test"]
    assert body["notes"] == "Test note"


@patch("requests.get")
def test_list_documents(mock_get, mock_list_response):
    mock_get.return_value = MockResponse(mock_list_response)

    reader = create_readwise_reader("test-key")
    documents = reader.list_documents(
        locations=["new"],
        updated_after=datetime(2024, 3, 20, tzinfo=timezone.utc),
    )

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args.kwargs
    assert call_kwargs["headers"] == {"Authorization": "Token test-key"}
    assert call_kwargs["url"] == "https://readwise.io/api/v3/list/"
    assert call_kwargs["params"] == {
        "location": "new",
        "updatedAfter": "2024-03-20T00:00:00+00:00",
    }

    assert len(documents) == 1
    doc = documents[0]
    assert isinstance(doc, Document)
    assert doc.id == "01gwfvp9pyaabcdgmx14f6ha0"
    assert doc.title == "Test Article 1"
    assert doc.tags == ["test"]
    assert doc.reading_progress == 0.5


@patch("requests.get")
def test_list_documents_pagination(mock_get):
    # First page response
    first_page = {
        "count": 2,
        "nextPageCursor": "next_page_token",
        "results": [
            {
                "id": "doc1",
                "url": "https://readwise.io/doc1",
                "source_url": "https://example.com/article1",
                "title": "Article 1",
                "author": "Author 1",
                "source": "Reader RSS",
                "category": "article",
                "location": "new",
                "tags": {},
                "notes": "",
                "site_name": "Example",
                "word_count": 100,
                "summary": "Summary 1",
                "reading_progress": 0,
                "created_at": "2024-03-20T10:00:00Z",
                "updated_at": "2024-03-20T10:00:00Z",
                "saved_at": "2024-03-20T10:00:00Z",
                "last_moved_at": "2024-03-20T10:00:00Z",
                "first_opened_at": None,
                "last_opened_at": None,
                "published_date": None,
                "image_url": None,
                "parent_id": None,
            }
        ],
    }

    # Second page response
    second_page = {
        "count": 2,
        "nextPageCursor": None,
        "results": [
            {
                "id": "doc2",
                "url": "https://readwise.io/doc2",
                "source_url": "https://example.com/article2",
                "title": "Article 2",
                "author": "Author 2",
                "source": "Reader RSS",
                "category": "article",
                "location": "new",
                "tags": {},
                "notes": "",
                "site_name": "Example",
                "word_count": 200,
                "summary": "Summary 2",
                "reading_progress": 0,
                "created_at": "2024-03-20T10:00:00Z",
                "updated_at": "2024-03-20T10:00:00Z",
                "saved_at": "2024-03-20T10:00:00Z",
                "last_moved_at": "2024-03-20T10:00:00Z",
                "first_opened_at": None,
                "last_opened_at": None,
                "published_date": None,
                "image_url": None,
                "parent_id": None,
            }
        ],
    }

    mock_get.side_effect = [
        MockResponse(first_page),
        MockResponse(second_page),
    ]

    reader = create_readwise_reader("test-key")
    documents = reader.list_documents(locations=["new"])

    assert len(documents) == 2
    assert documents[0].id == "doc1"
    assert documents[1].id == "doc2"
    assert mock_get.call_count == 2

    # Check first call
    first_call = mock_get.call_args_list[0]
    assert first_call.kwargs["params"] == {"location": "new"}

    # Check second call
    second_call = mock_get.call_args_list[1]
    assert second_call.kwargs["params"] == {
        "location": "new",
        "pageCursor": "next_page_token",
    }
