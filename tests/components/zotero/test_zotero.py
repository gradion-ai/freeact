import json
from unittest.mock import MagicMock, patch

import pytest

from gradion_incubator.skills.zotero.api import Document, Link
from gradion_incubator.skills.zotero.impl import GroupLibraryImpl


@pytest.fixture
def mock_zotero():
    with patch("pyzotero.zotero.Zotero") as mock:
        # Mock collections response
        collections = [
            {
                "key": "ABC123",
                "version": 1,
                "data": {
                    "name": "Papers",
                    "parentCollection": False,
                },
            },
            {
                "key": "DEF456",
                "version": 2,
                "data": {
                    "name": "ML Papers",
                    "parentCollection": "ABC123",
                },
            },
        ]

        # Mock items response
        items = [
            {
                "key": "ITEM789",
                "version": 3,
                "data": {
                    "itemType": "journalArticle",
                    "title": "Test Paper",
                    "url": "https://arxiv.org/abs/1234.5678",
                    "abstractNote": "Test abstract",
                    "collections": ["ABC123"],
                    "tags": [{"tag": "machine learning"}],
                    "date": "2023-01-01",
                },
            },
            {
                "key": "ATT101",
                "version": 4,
                "data": {
                    "itemType": "attachment",
                    "linkMode": "linked_url",
                    "title": "Supplementary",
                    "url": "https://example.com/supp",
                    "parentItem": "ITEM789",
                },
            },
        ]

        # Configure mock
        mock_instance = mock.return_value
        mock_instance.everything = lambda x: x
        mock_instance.collections.return_value = collections
        mock_instance.items.return_value = items
        mock_instance.deleted.return_value = {"collections": [], "items": []}
        mock_instance.trash.return_value = []

        yield mock_instance


@pytest.fixture
def temp_index(tmp_path):
    return tmp_path / "index.json"


def test_sync(mock_zotero, temp_index):
    library = GroupLibraryImpl(123, "fake-key", temp_index)
    library.sync()

    # Verify the index was created and saved
    assert temp_index.exists()
    with open(temp_index) as f:
        index = json.load(f)
        assert len(index["collections"]) == 2
        assert len(index["items"]) == 2


def test_root_structure(mock_zotero, temp_index):
    library = GroupLibraryImpl(123, "fake-key", temp_index)
    library.sync()
    root = library.root()

    # Test collection structure
    assert len(root.collections) == 1
    papers = root.collections[0]
    assert papers.name == "Papers"
    assert len(papers.collections) == 1
    assert papers.collections[0].name == "ML Papers"

    # Test documents
    assert len(papers.documents) == 1
    doc = papers.documents[0]
    assert doc.title == "Test Paper"
    assert doc.url == "https://arxiv.org/abs/1234.5678"
    assert doc.abstract == "Test abstract"
    assert doc.tags == ["machine learning"]
    assert str(doc.date) == "2023-01-01"

    # Test attachments
    assert len(doc.attachments) == 1
    attachment = doc.attachments[0]
    assert isinstance(attachment, Link)
    assert attachment.url == "https://example.com/supp"
    assert attachment.title == "Supplementary"


def test_attach_link(mock_zotero, temp_index):
    library = GroupLibraryImpl(123, "fake-key", temp_index)
    library.sync()

    # Mock the item template and create_items methods
    mock_zotero.item_template.return_value = {
        "url": "",
        "title": "",
        "note": "",
    }
    mock_zotero.create_items = MagicMock()

    # Get a document and attach a link
    doc = library.root().collections[0].documents[0]
    library.attach_link(document=doc, url="https://example.com/new", title="New Link", note="Test note")

    # Verify the API was called correctly
    mock_zotero.item_template.assert_called_with(itemtype="attachment", linkmode="linked_url")

    expected_attachment = {"url": "https://example.com/new", "title": "New Link", "note": "Test note"}
    mock_zotero.create_items.assert_called_with([expected_attachment], parentid=doc.key)


def test_document_methods(mock_zotero, temp_index):
    library = GroupLibraryImpl(123, "fake-key", temp_index)
    library.sync()
    root = library.root()

    # Test get_document
    doc = root.get_document("ITEM789")
    assert isinstance(doc, Document)
    assert doc.key == "ITEM789"

    # Test document not found
    assert root.get_document("NONEXISTENT") is None

    # Test sub_documents
    docs = root.sub_documents()
    assert len(docs) == 1
    assert docs[0].key == "ITEM789"


def test_collection_methods(mock_zotero, temp_index):
    library = GroupLibraryImpl(123, "fake-key", temp_index)
    library.sync()
    root = library.root()

    # Test sub_collections
    collections = root.sub_collections()
    assert len(collections) == 3  # Root + Papers + ML Papers
    assert collections[0].name == "Root"
    assert collections[1].name == "Papers"
    assert collections[2].name == "ML Papers"
