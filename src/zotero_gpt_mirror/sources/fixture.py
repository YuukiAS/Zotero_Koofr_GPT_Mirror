from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zotero_gpt_mirror.models import Author, LibraryItem, PdfAttachment


def default_fixture_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "tests" / "fixtures"


class FixtureSource:
    def __init__(self, fixture_dir: Path | None = None) -> None:
        self.fixture_dir = fixture_dir or default_fixture_dir()

    def scan(self) -> list[LibraryItem]:
        library_path = self.fixture_dir / "library.json"
        with library_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        items = payload.get("items", [])
        return [self._item_from_json(item) for item in items]

    def _item_from_json(self, data: dict[str, Any]) -> LibraryItem:
        attachments = []
        for attachment in data.get("attachments", []):
            raw_path = Path(attachment["source_path"])
            source_path = raw_path if raw_path.is_absolute() else self.fixture_dir / raw_path
            attachments.append(
                PdfAttachment(
                    attachment_key=attachment["attachment_key"],
                    source_path=source_path,
                    filename=attachment["filename"],
                    mime_type=attachment.get("mime_type", "application/octet-stream"),
                    title=attachment.get("title"),
                )
            )
        return LibraryItem(
            item_key=data["item_key"],
            item_type=data.get("item_type", "journalArticle"),
            title=data.get("title"),
            authors=tuple(Author(name=name) for name in data.get("authors", [])),
            year=str(data["year"]) if data.get("year") not in (None, "") else None,
            doi=data.get("doi") or None,
            url=data.get("url") or None,
            abstract=data.get("abstract") or None,
            collections=tuple(data.get("collections", [])),
            tags=tuple(data.get("tags", [])),
            attachments=tuple(attachments),
        )
