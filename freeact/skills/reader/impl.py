import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

import requests
from dateutil.parser import parse

from freeact.skills.reader.api import Document, ReadwiseReader


@dataclass
class DocumentsPage:
    documents: List[Document]
    next_page_cursor: str | None


class ReadwiseReaderImpl(ReadwiseReader):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ["READWISE_API_KEY"]
        self.base_url = "https://readwise.io/api/v3"

    def save_document_url(
        self,
        url: str,
        location: str | None = None,
        category: str | None = None,
        tags: List[str] | None = None,
        note: str | None = None,
    ):
        self._save(
            {"url": url},
            location,
            category,
            tags,
            note,
        )

    def save_document_html(
        self,
        html: str,
        title: str,
        location: str | None = None,
        category: str | None = None,
        tags: List[str] | None = None,
        note: str | None = None,
    ):
        self._save(
            {
                "url": f"https://gradion.ai#document-{uuid4()}",
                "html": html,
                "title": title,
                "should_clean_html": True,
                "author": "Gradion AI",
            },
            location,
            category,
            tags,
            note,
        )

    def _save(
        self,
        body: Dict[str, Any],
        location: str | None = None,
        category: str | None = None,
        tags: List[str] | None = None,
        note: str | None = None,
    ):
        _body = body.copy()
        if location:
            _body["location"] = location
        if category:
            _body["category"] = category
        if tags:
            _body["tags"] = tags
        if note:
            _body["notes"] = note

        response = requests.post(
            url=f"{self.base_url}/save/",
            headers={"Authorization": f"Token {self.api_key}"},
            json=_body,
        )
        response.raise_for_status()

    def list_documents(
        self,
        locations: List[str] | None = None,
        updated_after: datetime | None = None,
    ) -> List[Document]:
        if not locations:
            return self._list_documents_at(updated_after=updated_after)

        documents = []
        for location in locations:
            documents.extend(self._list_documents_at(location=location, updated_after=updated_after))
        return documents

    def _list_documents_at(
        self,
        location: str | None = None,
        updated_after: datetime | None = None,
    ) -> List[Document]:
        documents = []
        next_cursor = None

        while True:
            page = self._list_documents_page(updated_after=updated_after, location=location, page_cursor=next_cursor)

            documents.extend(page.documents)
            next_cursor = page.next_page_cursor

            if not next_cursor:
                break

        return documents

    def _list_documents_page(
        self,
        updated_after: datetime | None = None,
        location: str | None = None,
        page_cursor: str | None = None,
    ) -> DocumentsPage:
        params = {}
        if updated_after:
            params["updatedAfter"] = updated_after.isoformat()
        if location:
            params["location"] = location
        if page_cursor:
            params["pageCursor"] = page_cursor

        data = requests.get(
            url=f"{self.base_url}/list/",
            headers={"Authorization": f"Token {self.api_key}"},
            params=params,
        ).json()

        return DocumentsPage(
            documents=[self._parse_document(doc) for doc in data["results"]],
            next_page_cursor=data.get("nextPageCursor"),
        )

    @classmethod
    def _parse_datetime(cls, field: str, data: dict) -> datetime | None:
        if value := data.get(field):
            if isinstance(value, str):
                return parse(value)
            elif isinstance(value, int):
                # value is in milliseconds
                return datetime.fromtimestamp(value / 1000)
        return None

    @classmethod
    def _parse_document(cls, data: Dict) -> Document:
        return Document(
            id=data["id"],
            url=data["url"],
            source_url=data["source_url"],
            title=data["title"],
            author=data["author"],
            source=data["source"],
            summary=data["summary"],
            category=data["category"],
            location=data["location"],
            tags=list(data["tags"].keys()),
            note=data["notes"],
            site_name=data["site_name"],
            word_count=data["word_count"],
            reading_progress=float(data["reading_progress"]),
            created_at=parse(data["created_at"]),
            updated_at=parse(data["updated_at"]),
            saved_at=parse(data["saved_at"]),
            last_moved_at=parse(data["last_moved_at"]),
            first_opened_at=cls._parse_datetime("first_opened_at", data),
            last_opened_at=cls._parse_datetime("last_opened_at", data),
            published_date=cls._parse_datetime("published_date", data),
            image_url=data["image_url"],
            parent_id=data["parent_id"],
        )
