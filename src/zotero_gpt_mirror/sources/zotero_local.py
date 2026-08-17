from __future__ import annotations

import json
import urllib.error
import urllib.request

from zotero_gpt_mirror.models import LibraryItem
from zotero_gpt_mirror.sources.base import SourceUnavailableError


DEFAULT_LOCAL_API = "http://127.0.0.1:23119/api/"


class ZoteroLocalSource:
    def __init__(self, api_url: str = DEFAULT_LOCAL_API, timeout_seconds: float = 2.0) -> None:
        self.api_url = api_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds

    def scan(self) -> list[LibraryItem]:
        self.check_available()
        raise SourceUnavailableError(
            "Zotero Local API parsing is reserved for the next phase.\n"
            "Use `--source fixture` to test the exporter without Zotero."
        )

    def check_available(self) -> None:
        try:
            with urllib.request.urlopen(self.api_url, timeout=self.timeout_seconds) as response:
                body = response.read(2048)
                if response.status >= 400:
                    raise OSError(f"HTTP {response.status}")
                if body:
                    json.loads(body.decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise SourceUnavailableError(
                f"Zotero Local API is not available at {self.api_url}\n\n"
                "This is expected if Zotero is not installed or not running.\n"
                "Use `--source fixture` to test the exporter without Zotero."
            ) from exc
