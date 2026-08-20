from __future__ import annotations

import json
from pathlib import Path

from zotero_gpt_mirror.models import Author
from zotero_gpt_mirror.scan import summarize_items
from zotero_gpt_mirror.sources.zotero_local import (
    ZoteroLocalSource,
    parse_authors,
    parse_tags,
    parse_year,
)
from zotero_gpt_mirror.transports import HttpResponse


class FakeTransport:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses

    def get(self, path: str) -> HttpResponse:
        normalized = path.split("&start=", 1)[0]
        for key, value in self.responses.items():
            if normalized.startswith(key):
                if isinstance(value, tuple):
                    status, body = value
                else:
                    status, body = 200, value
                return HttpResponse(status=status, body=json.dumps(body), headers={})
        raise AssertionError(f"Unexpected path: {path}")


def zotero_item(key: str, data: dict) -> dict:
    return {"key": key, "data": {"key": key, **data}}


def test_creator_year_and_tag_parsing() -> None:
    assert parse_year("August 2026") == "2026"
    assert parse_year("not a date") is None
    assert parse_authors(
        [
            {"creatorType": "author", "firstName": "Alice", "lastName": "Smith"},
            {"creatorType": "editor", "firstName": "Ed", "lastName": "Ignored"},
            {"creatorType": "author", "name": "World Health Organization"},
        ]
    ) == (Author("Alice Smith"), Author("World Health Organization"))
    tags = parse_tags([{"tag": "Bayesian"}, {"tag": ""}, {"tag": "Bayesian"}, {"tag": "中文"}])
    assert tags == ("Bayesian", "中文")


def test_zotero_local_source_maps_realistic_json(monkeypatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "Paper Name.pdf"
    pdf_path.write_text("%PDF-1.4\n%%EOF\n", encoding="utf-8")

    def fake_file_url_to_wsl_path(file_url: str) -> Path:
        if "MISSING" in file_url:
            return tmp_path / "missing.pdf"
        return pdf_path

    monkeypatch.setattr(
        "zotero_gpt_mirror.sources.zotero_local.file_url_to_wsl_path",
        fake_file_url_to_wsl_path,
    )

    responses = {
        "users/0/items?limit=1": [],
        "users/0/collections?limit=100": [
            zotero_item("PARENT", {"name": "Research", "parentCollection": False}),
            zotero_item("CHILD", {"name": "Federated Learning", "parentCollection": "PARENT"}),
        ],
        "users/0/items/top?limit=100": [
            zotero_item(
                "ITEM1",
                {
                    "itemType": "journalArticle",
                    "title": "Federated Bayesian Learning",
                    "creators": [
                        {"creatorType": "author", "firstName": "Alice", "lastName": "Smith"},
                        {"creatorType": "editor", "firstName": "Ed", "lastName": "Ignored"},
                    ],
                    "date": "2026-08-20",
                    "DOI": "10.1000/test",
                    "url": "https://example.test/paper",
                    "abstractNote": "Anonymous abstract.",
                    "tags": [{"tag": "Bayesian"}, {"tag": "Bayesian"}, {"tag": "中文"}],
                    "collections": ["CHILD"],
                },
            ),
            zotero_item("NOPDF", {"itemType": "journalArticle", "title": "No PDF", "creators": []}),
            zotero_item("MISSING", {"itemType": "journalArticle", "title": "Missing PDF"}),
            zotero_item("MULTI", {"itemType": "journalArticle", "title": "Multiple PDF"}),
            zotero_item("ATTACH", {"itemType": "attachment", "title": "Top-level attachment ignored"}),
        ],
        "users/0/items/ITEM1/children?limit=100": [
            zotero_item(
                "ATT1",
                {
                    "itemType": "attachment",
                    "title": "Publisher PDF",
                    "filename": "Paper Name.pdf",
                    "contentType": "application/pdf",
                },
            ),
            zotero_item("HTML1", {"itemType": "attachment", "filename": "snapshot.html", "contentType": "text/html"}),
        ],
        "users/0/items/NOPDF/children?limit=100": [],
        "users/0/items/MISSING/children?limit=100": [
            zotero_item("MISSATT", {"itemType": "attachment", "filename": "missing.pdf", "contentType": "application/pdf"})
        ],
        "users/0/items/MULTI/children?limit=100": [
            zotero_item("MULTIA", {"itemType": "attachment", "filename": "main.pdf", "contentType": "application/pdf"}),
            zotero_item("MULTIB", {"itemType": "attachment", "filename": "supp.pdf", "contentType": "application/pdf"}),
        ],
        "users/0/items/ATT1/file/view/url": "file:///C:/Users/Alice/Zotero/storage/ITEM1/Paper%20Name.pdf",
        "users/0/items/MISSATT/file/view/url": "file:///C:/MISSING/missing.pdf",
        "users/0/items/MULTIA/file/view/url": "file:///C:/Users/Alice/Zotero/storage/MULTI/main.pdf",
        "users/0/items/MULTIB/file/view/url": "file:///C:/MISSING/supp.pdf",
    }

    source = ZoteroLocalSource(transport=FakeTransport(responses))
    items = source.scan()
    first = items[0]
    assert first.item_key == "ITEM1"
    assert first.authors[0].name == "Alice Smith"
    assert first.year == "2026"
    assert first.url == "https://example.test/paper"
    assert first.collections == ("Research / Federated Learning",)
    assert first.tags == ("Bayesian", "中文")
    assert first.attachments[0].source_path == pdf_path

    summary = summarize_items(items)
    assert summary.bibliographic_items == 4
    assert summary.items_with_one_pdf == 2
    assert summary.items_with_multiple_pdfs == 1
    assert summary.exportable_pdf_attachments == 2
    assert summary.no_pdf_attachment == 1
    assert summary.missing_local_attachment == 2
    assert summary.ambiguous_primary_items == 1
