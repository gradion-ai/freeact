import json
from pathlib import Path
from typing import Any, Dict, List

from pyzotero import zotero

from gradion.components.zotero.api import (
    Attachment,
    Collection,
    Document,
    GroupLibrary,
    Link,
    Node,
    Note,
)


class Index:
    def __init__(self, path: Path):
        self.path = path
        self.collections: Dict[str, Any] = {}
        self.items: Dict[str, Any] = {}
        self.version = 0

    def update(
        self,
        collections: List[Dict[str, Any]],
        items: List[Dict[str, Any]],
        removed: List[str],
    ):
        for collection in collections:
            self.collections[collection["key"]] = collection
            self.version = max(self.version, collection["version"])

        for item in items:
            self.items[item["key"]] = item
            self.version = max(self.version, item["version"])

        for key in removed:
            if key in self.collections:
                del self.collections[key]
            if key in self.items:
                del self.items[key]

    def load(self):
        if self.path.exists():
            with self.path.open("r") as f:
                persistent_index = json.load(f)
        else:
            persistent_index = {
                "collections": [],
                "items": [],
            }

        # reset index
        self.collections = {}
        self.items = {}
        self.version = 0

        # rebuild from scratch
        self.update(
            collections=persistent_index["collections"],
            items=persistent_index["items"],
            removed=[],
        )

    def save(self, indent: int | None = 2):
        self.path.parent.mkdir(parents=True, exist_ok=True)

        persistent_index = {
            "collections": list(self.collections.values()),
            "items": list(self.items.values()),
        }

        with self.path.open("w") as f:
            json.dump(persistent_index, f, indent=indent)


class GroupLibraryImpl(GroupLibrary):
    def __init__(self, group_id: int, api_key: str, index_path: Path = Path(".zotero", "index.json")):
        self.client = zotero.Zotero(group_id, "group", api_key)
        self.index = Index(index_path)
        self.index.load()

    def sync(self):
        # overrides the default limit of 100
        no_limit = self.client.everything

        collections = no_limit(self.client.collections(since=self.index.version))
        items = no_limit(self.client.items(since=self.index.version))

        # Keys of deleted collections and items
        deleted = self.client.deleted(since=self.index.version)
        # Keys of trashed items
        trashed = [t["key"] for t in no_limit(self.client.trash(since=self.index.version))]
        # Keys of trashed and deleted items
        removed = deleted["collections"] + deleted["items"] + trashed

        self.index.update(collections, items, removed)
        self.index.save()

    def root(self) -> Collection:
        root_collection = {
            "key": "root",
            "version": 0,
            "data": {
                "name": "Root",
                "parentCollection": "root",
            },
        }

        node_index: Dict[str, Node] = {}

        for key, collection in self.index.collections.items():
            _cn = self._create_collection_node(collection)
            if _cn is not None:
                node_index[key] = _cn

        for key, item in self.index.items.items():
            _in = self._create_content_node(item)
            if _in is not None:
                node_index[key] = _in

        root = self._create_collection_node(root_collection)

        for _, node in node_index.items():
            if node is None:
                continue

            match node:
                case Collection():
                    parent_key = node.source["data"]["parentCollection"]
                    if parent_key:
                        node.parent = node_index[parent_key]  # type: ignore
                        node.parent.collections.append(node)
                    else:
                        root.collections.append(node)
                        node.parent = root
                case Document():
                    collections = [node_index[c] for c in node.source["data"]["collections"]]

                    if collections:
                        node.collections = collections  # type: ignore
                        for collection in node.collections:
                            collection.documents.append(node)
                    else:
                        root.documents.append(node)
                        node.collections = [root]
                case Attachment():
                    document = node_index[node.source["data"]["parentItem"]]
                    document.attachments.append(node)  # type: ignore

        return root

    def attach_link(self, document: Document, url: str, title: str, note: str | None = None):
        attachment = self.client.item_template(itemtype="attachment", linkmode="linked_url")
        attachment["url"] = url
        attachment["title"] = title

        if note is not None:
            attachment["note"] = note

        self.client.create_items([attachment], parentid=document.key)

    @staticmethod
    def _create_collection_node(source: Dict[str, Any]) -> Collection:
        return Collection(source=source, parent=None)  # type: ignore

    @staticmethod
    def _create_content_node(source: Dict[str, Any]) -> Document | Attachment | None:
        item_type = source["data"]["itemType"]

        if item_type == "note":
            return Note(source=source, document=None)  # type: ignore
        elif item_type == "attachment" and source["data"]["linkMode"] == "linked_url":
            return Link(source=source, document=None)  # type: ignore
        elif "collections" in source["data"]:
            return Document(source=source)
        else:
            return None
