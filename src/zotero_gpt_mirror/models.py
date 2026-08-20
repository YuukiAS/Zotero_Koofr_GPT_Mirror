from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Author:
    name: str


@dataclass(frozen=True)
class PdfAttachment:
    attachment_key: str
    source_path: Path | None
    filename: str
    mime_type: str = "application/pdf"
    title: str | None = None


@dataclass(frozen=True)
class LibraryItem:
    item_key: str
    item_type: str
    title: str | None = None
    authors: tuple[Author, ...] = field(default_factory=tuple)
    year: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    collections: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    attachments: tuple[PdfAttachment, ...] = field(default_factory=tuple)

    def pdf_attachments(self) -> tuple[PdfAttachment, ...]:
        return tuple(
            attachment
            for attachment in self.attachments
            if attachment.mime_type.lower() == "application/pdf"
            or attachment.filename.lower().endswith(".pdf")
        )
