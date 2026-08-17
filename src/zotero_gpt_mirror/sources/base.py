from __future__ import annotations

from typing import Protocol

from zotero_gpt_mirror.models import LibraryItem


class SourceUnavailableError(RuntimeError):
    """Raised when a source cannot be scanned in normal user-facing flows."""


class LibrarySource(Protocol):
    def scan(self) -> list[LibraryItem]:
        """Return normalized library records."""
