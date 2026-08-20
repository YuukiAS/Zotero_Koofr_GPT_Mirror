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
                    "url": "",
                    "pdf_count": "1",
                    "primary_pdf": "Papers/2026/A.pdf",
                    "pdf_paths": "Papers/2026/A.pdf",
                    "attachment_status": "ATT:primary:available",
                    "collections": "",
                    "tags": "",
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
    item_entry = manifest["items"]["ITEM0001"]
    assert item_entry["attachments"][0]["source_file_size"] == pdf.stat().st_size
    assert item_entry["primary_status"] == "single"


def test_fixture_initial_export_writes_expected_tree(tmp_path: Path) -> None:
    output = tmp_path / "mirror"
    report = Exporter(output, Path.cwd()).export(FixtureSource())
    assert report.errors == []
    assert report.added == 12
    assert report.multiple_pdf_attachments == 1
    assert report.duplicate_pdfs_suppressed == 1
    assert (output / "_Index" / "library.csv").exists()
    assert (output / "_Index" / "manifest.json").exists()
    assert len(list((output / "Papers").rglob("*.pdf"))) == 15
    assert len(list((output / "Papers").rglob("*.md"))) == 12
    assert len(list((output / "Papers").rglob("*MULTIPDF11*.pdf"))) == 4
    assert len(list((output / "Papers").rglob("*MULTIPDF11*.md"))) == 1
    assert (output / "Papers" / "Unknown-Year").exists()


def test_second_export_skips_all_items(tmp_path: Path) -> None:
    output = tmp_path / "mirror"
    exporter = Exporter(output, Path.cwd())
    exporter.export(FixtureSource())
    report = exporter.export(FixtureSource())
    assert report.added == 0
    assert report.updated_pdf == 0
    assert report.updated_metadata == 0
    assert report.skipped == 12


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


def test_multiple_pdf_attachments_are_exported_without_error(tmp_path: Path) -> None:
    first = make_pdf(tmp_path / "one.pdf", "%PDF-1.4\none\n%%EOF\n")
    second = make_pdf(tmp_path / "two.pdf", "%PDF-1.4\ntwo\n%%EOF\n")
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
    assert report.multiple_pdf_attachments == 1
    assert report.errors == []
    assert len(list((tmp_path / "out" / "Papers").rglob("*.pdf"))) == 2
    assert len(list((tmp_path / "out" / "Papers").rglob("*.md"))) == 1


def test_duplicate_pdfs_in_multi_item_are_suppressed_with_provenance(tmp_path: Path) -> None:
    first = make_pdf(tmp_path / "one.pdf", "%PDF-1.4\nsame\n%%EOF\n")
    second = make_pdf(tmp_path / "two.pdf", "%PDF-1.4\nsame\n%%EOF\n")
    item = LibraryItem(
        item_key="DUPPDF",
        item_type="journalArticle",
        title="Duplicate PDFs",
        attachments=(
            PdfAttachment("A", first, "paper.pdf", "application/pdf", title="PDF"),
            PdfAttachment("B", second, "paper-copy.pdf", "application/pdf", title="Accepted Manuscript"),
        ),
    )
    output = tmp_path / "out"
    report = Exporter(output, Path.cwd()).export(StaticSource([item]))
    manifest = load_manifest(output)
    assert report.duplicate_pdfs_suppressed == 1
    assert len(list((output / "Papers").rglob("*.pdf"))) == 1
    attachments = manifest["items"]["DUPPDF"]["attachments"]
    assert attachments[1]["duplicate_of"] == "A"
    assert attachments[1]["output_pdf_relative_path"] == attachments[0]["output_pdf_relative_path"]


def test_ambiguous_primary_exports_all_with_suffixes(tmp_path: Path) -> None:
    first = make_pdf(tmp_path / "publisher.pdf", "%PDF-1.4\npublisher\n%%EOF\n")
    second = make_pdf(tmp_path / "accepted.pdf", "%PDF-1.4\naccepted\n%%EOF\n")
    item = LibraryItem(
        item_key="AMBIGPDF",
        item_type="journalArticle",
        title="Ambiguous Versions",
        attachments=(
            PdfAttachment("PUB", first, "publisher.pdf", "application/pdf", title="Publisher Version"),
            PdfAttachment("ACC", second, "accepted.pdf", "application/pdf", title="Accepted Manuscript"),
        ),
    )
    output = tmp_path / "out"
    report = Exporter(output, Path.cwd()).export(StaticSource([item]))
    manifest = load_manifest(output)
    assert report.ambiguous_primary_items == 1
    assert manifest["items"]["AMBIGPDF"]["primary_status"] == "ambiguous"
    names = sorted(path.name for path in (output / "Papers").rglob("*.pdf"))
    assert all(" -- " in name for name in names)
