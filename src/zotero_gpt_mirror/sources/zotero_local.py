from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zotero_gpt_mirror.models import Author, LibraryItem, PdfAttachment
from zotero_gpt_mirror.paths import PathConversionError, file_url_to_wsl_path
from zotero_gpt_mirror.sources.base import SourceUnavailableError
from zotero_gpt_mirror.transports import (
    AutoTransport,
    DirectHttpTransport,
    LocalApiTransport,
    TransportError,
    WindowsInteropTransport,
)


DEFAULT_LOCAL_API = "http://127.0.0.1:23119/api/"
EXCLUDED_TOP_LEVEL_TYPES = {"attachment", "note", "annotation"}
PAGE_LIMIT = 100


@dataclass(frozen=True)
class CollectionNode:
    key: str
    name: str
    parent_key: str | None


class ZoteroLocalSource:
    def __init__(
        self,
        api_url: str = DEFAULT_LOCAL_API,
        timeout_seconds: float = 5.0,
        transport: LocalApiTransport | None = None,
        transport_mode: str = "auto",
    ) -> None:
        self.api_url = api_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds
        self.transport = transport or make_transport(self.api_url, timeout_seconds, transport_mode)
        self._collection_paths: dict[str, str] | None = None

    def scan(self) -> list[LibraryItem]:
        self.check_available()
        collection_paths = self.collection_paths()
        items = []
        for raw_item in self.get_paginated_json("users/0/items/top"):
            data = raw_item.get("data", {})
            if data.get("itemType") in EXCLUDED_TOP_LEVEL_TYPES:
                continue
            items.append(self.item_from_zotero(raw_item, collection_paths))
        return items

    def check_available(self) -> None:
        response = self.get("users/0/items?limit=1")
        if response.status == 403:
            raise SourceUnavailableError(
                "Zotero Local API returned 403.\n\n"
                "In Zotero, enable: Allow other applications on this computer to communicate with Zotero."
            )
        if response.status >= 400:
            raise SourceUnavailableError(
                f"Zotero Local API returned HTTP {response.status} at {self.api_url}"
            )

    def get(self, path: str):
        try:
            return self.transport.get(path)
        except TransportError as exc:
            raise SourceUnavailableError(
                f"Zotero Local API is not available at {self.api_url}\n\n"
                "This is expected if Zotero is not installed, not running, or Windows interop is unavailable.\n"
                "Use `--source fixture` to test the exporter without Zotero."
            ) from exc

    def get_paginated_json(self, path: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        start = 0
        while True:
            separator = "&" if "?" in path else "?"
            response = self.get(f"{path}{separator}limit={PAGE_LIMIT}&start={start}")
            if response.status >= 400:
                raise SourceUnavailableError(f"Zotero Local API returned HTTP {response.status} for {path}")
            page = json.loads(response.body or "[]")
            if not isinstance(page, list):
                raise SourceUnavailableError(f"Expected Zotero list response for {path}")
            results.extend(page)
            if len(page) < PAGE_LIMIT:
                return results
            start += PAGE_LIMIT

    def collection_paths(self) -> dict[str, str]:
        if self._collection_paths is not None:
            return self._collection_paths
        nodes: dict[str, CollectionNode] = {}
        for raw_collection in self.get_paginated_json("users/0/collections"):
            data = raw_collection.get("data", {})
            key = raw_collection.get("key") or data.get("key")
            name = clean_text(data.get("name"))
            if key and name:
                nodes[key] = CollectionNode(
                    key=key,
                    name=name,
                    parent_key=data.get("parentCollection") or None,
                )
        paths = {key: collection_path(key, nodes, set()) for key in nodes}
        self._collection_paths = paths
        return paths

    def item_from_zotero(self, raw_item: dict[str, Any], collection_paths: dict[str, str]) -> LibraryItem:
        data = raw_item.get("data", {})
        key = raw_item.get("key") or data.get("key")
        if not key:
            raise SourceUnavailableError("Zotero item is missing key.")
        children = self.children_for_item(key)
        attachments = tuple(self.attachment_from_zotero(child) for child in children if is_attachment(child))
        collection_names = tuple(
            sorted(
                collection_paths.get(collection_key, collection_key)
                for collection_key in data.get("collections", [])
                if collection_key
            )
        )
        return LibraryItem(
            item_key=key,
            item_type=data.get("itemType", ""),
            title=clean_text(data.get("title")),
            authors=parse_authors(data.get("creators", [])),
            year=parse_year(data.get("date")),
            doi=clean_text(data.get("DOI")),
            url=clean_text(data.get("url")),
            abstract=clean_text(data.get("abstractNote")),
            collections=collection_names,
            tags=parse_tags(data.get("tags", [])),
            attachments=attachments,
        )

    def children_for_item(self, item_key: str) -> list[dict[str, Any]]:
        quoted_key = urllib.parse.quote(item_key, safe="")
        return self.get_paginated_json(f"users/0/items/{quoted_key}/children")

    def attachment_from_zotero(self, raw_child: dict[str, Any]) -> PdfAttachment:
        data = raw_child.get("data", {})
        key = raw_child.get("key") or data.get("key") or ""
        filename = clean_text(data.get("filename")) or clean_text(data.get("title")) or f"{key}.pdf"
        content_type = clean_text(data.get("contentType")) or "application/octet-stream"
        source_path = self.attachment_wsl_path(key) if is_pdf_attachment_data(data) else None
        return PdfAttachment(
            attachment_key=key,
            source_path=source_path,
            filename=filename,
            mime_type=content_type,
            title=clean_text(data.get("title")),
        )

    def attachment_wsl_path(self, attachment_key: str) -> Path | None:
        quoted_key = urllib.parse.quote(attachment_key, safe="")
        response = self.get(f"users/0/items/{quoted_key}/file/view/url")
        if response.status >= 400:
            return None
        file_url = parse_file_url_response(response.body)
        if not file_url:
            return None
        try:
            return file_url_to_wsl_path(file_url)
        except PathConversionError:
            return None


def make_transport(api_url: str, timeout_seconds: float, transport_mode: str) -> LocalApiTransport:
    if transport_mode == "auto":
        return AutoTransport(api_url, timeout_seconds)
    if transport_mode == "direct":
        return DirectHttpTransport(api_url, timeout_seconds)
    if transport_mode == "windows-interop":
        return WindowsInteropTransport(api_url, timeout_seconds)
    raise ValueError(f"Unknown Zotero transport mode: {transport_mode}")


def is_attachment(raw_child: dict[str, Any]) -> bool:
    return raw_child.get("data", {}).get("itemType") == "attachment"


def is_pdf_attachment_data(data: dict[str, Any]) -> bool:
    content_type = str(data.get("contentType") or "").lower()
    filename = str(data.get("filename") or data.get("title") or "").lower()
    return content_type == "application/pdf" or filename.endswith(".pdf")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_authors(creators: list[dict[str, Any]]) -> tuple[Author, ...]:
    authors = []
    for creator in creators:
        if creator.get("creatorType") != "author":
            continue
        name = clean_text(creator.get("name"))
        if not name:
            first = clean_text(creator.get("firstName"))
            last = clean_text(creator.get("lastName"))
            name = " ".join(part for part in (first, last) if part)
        if name:
            authors.append(Author(name=name))
    return tuple(authors)


def parse_year(date_value: Any) -> str | None:
    text = clean_text(date_value)
    if not text:
        return None
    match = re.search(r"\b(18|19|20|21)\d{2}\b", text)
    return match.group(0) if match else None


def parse_tags(tags: list[dict[str, Any]]) -> tuple[str, ...]:
    cleaned = {tag for tag_data in tags if (tag := clean_text(tag_data.get("tag")))}
    return tuple(sorted(cleaned))


def collection_path(key: str, nodes: dict[str, CollectionNode], seen: set[str]) -> str:
    node = nodes[key]
    if not node.parent_key or node.parent_key not in nodes or node.parent_key in seen:
        return node.name
    return f"{collection_path(node.parent_key, nodes, seen | {key})} / {node.name}"


def parse_file_url_response(body: str) -> str | None:
    text = body.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, str):
            return parsed
        if isinstance(parsed, dict):
            value = parsed.get("url") or parsed.get("file")
            return str(value) if value else None
    except json.JSONDecodeError:
        pass
    return text
