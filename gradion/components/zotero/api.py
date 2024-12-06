import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from dateutil.parser import ParserError, parse

B = TypeVar("B")


@dataclass
class Node(ABC):
    source: Dict[str, Any]

    @property
    def key(self) -> str:
        return self.source["key"]

    @property
    def version(self) -> int:
        return self.source["version"]

    def fold(self, z: B, op: Callable[[B, "Node", int], B], level: int = 0) -> B:
        return op(z, self, level)

    def filter(self, pred: Callable[["Node"], bool]) -> List["Node"]:
        def op(z: List["Node"], node: "Node", level: int):
            if pred(node):
                z.append(node)
            return z

        return self.fold(z=[], op=op)

    def print(self):
        def op(z: None, node: "Node", level: int):
            print(f"{'  ' * level}- {str(node)} (key={node.key}, v={node.version})")

        self.fold(z=None, op=op)

    def max_version(self) -> int:
        def op(z: int, node: "Node", level: int):
            return max(z, node.version)

        return self.fold(z=0, op=op)


@dataclass
class Collection(Node):
    """A Zotero collection."""

    parent: "Collection"
    """The parent collection. For root collections, this is self."""

    collections: List["Collection"] = field(default_factory=list)
    """The sub-collections in this collection (not recursively)."""

    documents: List["Document"] = field(default_factory=list)
    """The documents in this collection (not recursively)."""

    @property
    def name(self) -> str:
        return self.source["data"]["name"]

    def __repr__(self):
        return f"[{self.name}]"

    def fold(self, z: B, op: Callable[[B, Node, int], B], level: int = 0) -> B:
        z = op(z, self, level)
        for document in self.documents:
            z = document.fold(z, op, level + 1)
        for child in self.collections:
            z = child.fold(z, op, level + 1)
        return z

    def sub_collections(self) -> List["Collection"]:
        """The sub-collections in this collection (recursively). Also includes this collection."""
        return self.filter(lambda node: isinstance(node, Collection))  # type: ignore

    def sub_documents(self) -> List["Document"]:
        """The documents in this collection and all sub-collections (recursively)."""
        document_keys = set()

        def pred(node: Node) -> bool:
            if not isinstance(node, Document):
                return False
            if node.key in document_keys:
                return False
            else:
                document_keys.add(node.key)
                return True

        return self.filter(pred)  # type: ignore

    def get_document(self, key: str) -> Optional["Document"]:
        """Get a document by its key. The tree rooted at this collection is searched."""
        documents = self.filter(lambda node: isinstance(node, Document) and node.key == key)
        return documents[0] if documents else None  # type: ignore


@dataclass
class Document(Node):
    """A Zotero document (e.g., a paper, article, etc.)."""

    collections: List[Collection] = field(default_factory=list)
    """The collections containing this document (not recursively)."""

    attachments: List["Attachment"] = field(default_factory=list)
    """The attachments of this document."""

    @property
    def url(self) -> str:
        """The URL of this document."""
        return self.source["data"]["url"]

    @property
    def title(self) -> str:
        """The title of this document."""
        return self.source["data"]["title"]

    @property
    def abstract(self) -> str | None:
        """The abstract of this document."""
        return self.source["data"].get("abstractNote", None)

    @property
    def tags(self) -> List[str]:
        """The tags of this document."""
        tags = []
        for tag in self.source["data"]["tags"]:
            tags.append(tag["tag"])
        return tags

    @property
    def date(self) -> date | None:
        """The publication date of this document."""
        date_str = self.source["data"].get("date")
        if date_str:
            try:
                return parse(date_str).date()
            except ParserError:
                return None
        else:
            return None

    def __repr__(self):
        return self.title

    def fold(self, z: B, op: Callable[[B, Node, int], B], level: int = 0) -> B:
        z = op(z, self, level)
        for attachment in self.attachments:
            z = attachment.fold(z, op, level + 1)
        return z


@dataclass
class Attachment(Node):
    """An attachment of a document."""

    document: Document
    """The document that this attachment belongs to."""


@dataclass
class Note(Attachment):
    """A note attached to a document."""

    @property
    def content(self) -> str:
        """The content of this note."""
        return self.source["data"]["note"]

    def __repr__(self):
        return f"Note: {self.content}"


@dataclass
class Link(Attachment):
    """A link attached to a document."""

    @property
    def url(self) -> str:
        """The URL of this link."""
        return self.source["data"]["url"]

    @property
    def title(self) -> str | None:
        """The title of this link."""
        return self.source["data"].get("title")

    @property
    def note(self) -> str | None:
        """The note of this link."""
        return self.source["data"].get("note")

    def __repr__(self):
        return f"Link: {self.url}"


class GroupLibrary(ABC):
    @abstractmethod
    def sync(self):
        """Sync this library from Zotero to the local index. This fetches the latest updates from Zotero."""

    @abstractmethod
    def root(self) -> Collection:
        """The root collection of the Zotero group library. This is the collection that contains all other collections and documents."""

    @abstractmethod
    def attach_link(self, document: Document, url: str, title: str, note: str | None = None):
        """Attach a link to a document. Only works if the provided ZOTERO_API_KEY has write access to the group."""


def load_group_library(
    group_id: int | None = None,
    api_key: str | None = None,
    index_path: Path = Path(".zotero", "index.json"),
) -> GroupLibrary:
    """Loads the Zotero group library identified by group_id.

    The library is loaded from the local index located at index_path. To obtain the latest
    updates from Zotero, the returned library object should be synced first with `sync()`.

    Args:
        group_id: The ID of the Zotero group. If not defined, it is read from the environment variable ZOTERO_GROUP_ID.
        api_key: The API key for the Zotero group. If not defined, it is read from the environment variable ZOTERO_API_KEY.
        index_path: The path to the local index.

    Returns:
        A GroupLibrary object.
    """
    from gradion.components.zotero.impl import GroupLibraryImpl

    return GroupLibraryImpl(
        group_id=group_id or int(os.environ["ZOTERO_GROUP_ID"]),
        api_key=api_key or os.environ["ZOTERO_API_KEY"],
        index_path=index_path,
    )
