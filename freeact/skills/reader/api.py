from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class Document:
    id: str
    """The ID of the document in Reader."""
    url: str
    """The URL of the document in Reader."""
    source_url: str
    """The URL of the original document."""
    title: str
    author: str
    source: str
    summary: str
    category: str
    """One of `article`, `email`, `rss`, `highlight`, `note`, `pdf`, `epub`, `tweet` or `video`."""
    location: str
    """One of `new`, `later`, `archive` or `feed`."""
    tags: List[str]
    """A list of document tags."""
    note: str
    """A top-level note of the document."""
    site_name: str
    word_count: int
    reading_progress: float
    created_at: datetime
    updated_at: datetime
    saved_at: datetime
    last_moved_at: datetime
    first_opened_at: datetime | None
    last_opened_at: datetime | None
    published_date: datetime | None
    image_url: str | None
    parent_id: str | None


class ReadwiseReader(ABC):
    @abstractmethod
    def save_document_url(
        self,
        url: str,
        location: str | None = None,
        category: str | None = None,
        tags: List[str] | None = None,
        note: str | None = None,
    ):
        """Saves a document to Readwise Reader by scraping it from the provided URL.

        Args:
            url: The URL of the document to save.
            location: The location to save the document to. Must be one of ["new", "later", "archive"].
                Defaults to None.
            category: The category of the document. Must be one of ["article", "pdf", "tweet", "video"].
                Defaults to None.
            tags: The tags to add to the document. Defaults to None.
            note: A note to add to the document. Defaults to None.
        """

    @abstractmethod
    def save_document_html(
        self,
        html: str,
        title: str,
        location: str | None = None,
        category: str | None = None,
        tags: List[str] | None = None,
        note: str | None = None,
    ):
        """Saves the provided HTML document to Reader.

        Args:
            html: The HTML content of the document to save.
            title: The title of the document.
            location: The location to save the document to. Must be one of ["new", "later", "archive"].
                Defaults to None.
            category: The category of the document. Must be one of ["article", "pdf", "tweet", "video"].
                Defaults to None.
            tags: The tags to add to the document. Defaults to None.
            note: A note to add to the document. Defaults to None.
        """

    @abstractmethod
    def list_documents(
        self,
        locations: List[str] | None = None,
        updated_after: datetime | None = None,
    ) -> List[Document]:
        """List documents saved in Readwise Reader.

        Args:
            locations: The locations to list documents from. Must be a subset of
                ["new", "later", "archive", "feed"]. Defaults to ["new", "later", "archive"].
            updated_after: Only list documents updated after this datetime. Defaults to None.

        Returns:
            List of Document objects.
        """


def create_readwise_reader(api_key: str | None = None) -> ReadwiseReader:
    """Creates a ReadwiseReader client instance.

    Args:
        api_key: The API key for the Readwise Reader API. If not provided, it is read from
            the environment variable READWISE_API_KEY.

    Returns:
        A ReadwiseReader instance.
    """
    from freeact.skills.reader.impl import ReadwiseReaderImpl

    return ReadwiseReaderImpl(api_key)
