from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from zotero_gpt_mirror.exporter import Exporter, render_library_csv, render_metadata_markdown
from zotero_gpt_mirror.manifest import load_manifest
from zotero_gpt_mirror.models import Author, LibraryItem, PdfAttachment
from zotero_gpt_mirror.sources.fixture import FixtureSource


class StaticSource:
    def __init__(self, items: list[LibraryItem]) -> None:
        self.items = items

    def scan(self) -> list[LibraryItem]:
        return self.items


class FailingSource:
    def scan(self) -> list[LibraryItem]:
        raise RuntimeError("scan failed")


def make_pdf(path: Path, text: str = "%PDF-1.4\n%%EOF\n") -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def make_item(pdf_path: Path, *, tag: str = "tag", title: str = "Stable Title") -> LibraryItem:
    return LibraryItem(
        item_key="ITEM0001",
        item_type="journalArticle",
        title=title,
        authors=(Author("Alice Smith"),),
        year="2026",
        doi="10.1000/test",
        abstract="Fixture abstract.",
        collections=("Collection",),
        tags=(tag,),
        attachments=(
            PdfAttachment(
                attachment_key="ATT0001",
                source_path=pdf_path,
                filename=pdf_path.name,
                mime_type="application/pdf",
            ),
        ),
    )


def test_metadata_markdown_omits_null_like_values() -> None:
    item = LibraryItem("KEY", "journalArticle", title="Title")
    markdown = render_metadata_markdown(item)
    assert "DOI:" not in markdown
    assert "None" not in markdown
    assert "null" not in markdown
    assert "Authors: Unknown" in markdown
    assert "Year: Unknown" in markdown


def test_library_csv_quotes_commas() -> None:
    item = LibraryItem("KEY", "journalArticle", title="A, B", authors=(Author("Alice Smith"),), year="2026")
    csv_text = render_library_csv(
        [
            {
                "item_key": item.item_key,
                "title": item.title or "",
                "authors": "Alice Smith",
                "year": "2026",
                "doi": "",
                "collections": "",
                "tags": "",
                "pdf_relative_path": "Papers/2026/A.pdf",
                "metadata_relative_path": "Papers/2026/A.md",
            }
        ]
    )
    assert '"A, B"' in csv_text


def test_manifest_round_trip_after_export(tmp_path: Path) -> None:
    pdf = make_pdf(tmp_path / "source.pdf")
    output = tmp_path / "out"
    report = Exporter(output, Path.cwd()).export(StaticSource([make_item(pdf)]))
    manifest = load_manifest(output)
    assert report.added == 1
    assert manifest["schema_version"] == 1
    assert manifest["items"]["ITEM0001"]["source_file_size"] == pdf.stat().st_size


def test_fixture_initial_export_writes_expected_tree(tmp_path: Path) -> None:
    output = tmp_path / "mirror"
    report = Exporter(output, Path.cwd()).export(FixtureSource())
    assert report.errors == []
    assert report.added == 11
    assert (output / "_Index" / "library.csv").exists()
    assert (output / "_Index" / "manifest.json").exists()
    assert len(list((output / "Papers").rglob("*.pdf"))) == 11
    assert len(list((output / "Papers").rglob("*.md"))) == 11
    assert (output / "Papers" / "Unknown-Year").exists()


def test_second_export_skips_all_items(tmp_path: Path) -> None:
    output = tmp_path / "mirror"
    exporter = Exporter(output, Path.cwd())
    exporter.export(FixtureSource())
    report = exporter.export(FixtureSource())
    assert report.added == 0
    assert report.updated_pdf == 0
    assert report.updated_metadata == 0
    assert report.skipped == 11


def test_metadata_change_only_updates_metadata(tmp_path: Path) -> None:
    pdf = make_pdf(tmp_path / "source.pdf")
    output = tmp_path / "out"
    exporter = Exporter(output, Path.cwd())
    exporter.export(StaticSource([make_item(pdf, tag="old")]))
    report = exporter.export(StaticSource([make_item(pdf, tag="new")]))
    assert report.updated_metadata == 1
    assert report.updated_pdf == 0


def test_pdf_change_updates_pdf(tmp_path: Path) -> None:
    pdf = make_pdf(tmp_path / "source.pdf")
    output = tmp_path / "out"
    exporter = Exporter(output, Path.cwd())
    exporter.export(StaticSource([make_item(pdf)]))
    pdf.write_text("%PDF-1.4\nchanged\n%%EOF\n", encoding="utf-8")
    os.utime(pdf, (pdf.stat().st_atime + 10, pdf.stat().st_mtime + 10))
    report = exporter.export(StaticSource([make_item(pdf)]))
    assert report.updated_pdf == 1


def test_deleted_outputs_are_restored(tmp_path: Path) -> None:
    pdf = make_pdf(tmp_path / "source.pdf")
    output = tmp_path / "out"
    exporter = Exporter(output, Path.cwd())
    exporter.export(StaticSource([make_item(pdf)]))
    exported_pdf = next(output.rglob("*.pdf"))
    exported_pdf.unlink()
    report = exporter.export(StaticSource([make_item(pdf)]))
    assert report.updated_pdf == 1
    assert exported_pdf.exists()


def test_dry_run_does_not_write_disk(tmp_path: Path) -> None:
    pdf = make_pdf(tmp_path / "source.pdf")
    output = tmp_path / "dry"
    report = Exporter(output, Path.cwd()).export(StaticSource([make_item(pdf)]), dry_run=True)
    assert report.added == 1
    assert not output.exists()


def test_source_scan_failure_preserves_old_manifest(tmp_path: Path) -> None:
    pdf = make_pdf(tmp_path / "source.pdf")
    output = tmp_path / "out"
    exporter = Exporter(output, Path.cwd())
    exporter.export(StaticSource([make_item(pdf)]))
    before = (output / "_Index" / "manifest.json").read_text(encoding="utf-8")
    with pytest.raises(RuntimeError):
        exporter.export(FailingSource())
    after = (output / "_Index" / "manifest.json").read_text(encoding="utf-8")
    assert after == before


def test_stale_items_are_marked_but_not_deleted(tmp_path: Path) -> None:
    pdf = make_pdf(tmp_path / "source.pdf")
    output = tmp_path / "out"
    exporter = Exporter(output, Path.cwd())
    exporter.export(StaticSource([make_item(pdf)]))
    exported_pdf = next(output.rglob("*.pdf"))
    report = exporter.export(StaticSource([]))
    manifest = json.loads((output / "_Index" / "manifest.json").read_text(encoding="utf-8"))
    assert report.stale == 1
    assert manifest["items"]["ITEM0001"]["status"] == "stale"
    assert exported_pdf.exists()


def test_multiple_pdf_attachments_report_error(tmp_path: Path) -> None:
    first = make_pdf(tmp_path / "one.pdf")
    second = make_pdf(tmp_path / "two.pdf")
    item = LibraryItem(
        item_key="MULTIPDF",
        item_type="journalArticle",
        title="Multiple PDFs",
        attachments=(
            PdfAttachment("A", first, "one.pdf", "application/pdf"),
            PdfAttachment("B", second, "two.pdf", "application/pdf"),
        ),
    )
    report = Exporter(tmp_path / "out", Path.cwd()).export(StaticSource([item]))
    assert report.errors == ["MULTIPDF: multiple PDF attachments are not supported in 0.1.0"]
    assert not (tmp_path / "out" / "Papers").exists()
