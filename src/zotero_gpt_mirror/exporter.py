from __future__ import annotations

import csv
import hashlib
import io
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from zotero_gpt_mirror.manifest import (
    EXPORTER_VERSION,
    SCHEMA_VERSION,
    atomic_write_text_if_changed,
    load_manifest,
    stable_json,
)
from zotero_gpt_mirror.models import LibraryItem
from zotero_gpt_mirror.naming import output_relative_paths, validate_output_dir
from zotero_gpt_mirror.sources.base import LibrarySource

MULTIVALUE_SEPARATOR = " | "


@dataclass
class ExportReport:
    added: int = 0
    updated_metadata: int = 0
    updated_pdf: int = 0
    skipped: int = 0
    stale: int = 0
    errors: list[str] = field(default_factory=list)

    def human_summary(self, dry_run: bool = False) -> str:
        prefix = "Would " if dry_run else ""
        lines = [
            f"{prefix}add: {self.added}",
            f"{prefix}update metadata: {self.updated_metadata}",
            f"{prefix}update PDF: {self.updated_pdf}",
            f"{prefix}skip: {self.skipped}",
            f"{prefix}mark stale: {self.stale}",
        ]
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
            lines.extend(f"- {error}" for error in self.errors)
        return "\n".join(lines)


class Exporter:
    def __init__(
        self,
        output_dir: Path,
        repo_root: Path,
        raw_output_value: str | Path | None = None,
        copy_pdf: bool = True,
        write_metadata: bool = True,
        write_index: bool = True,
    ) -> None:
        self.output_dir = output_dir
        self.repo_root = repo_root
        self.copy_pdf = copy_pdf
        self.write_metadata = write_metadata
        self.write_index = write_index
        validate_output_dir(output_dir, raw_output_value or output_dir, repo_root)

    def export(self, source: LibrarySource, dry_run: bool = False) -> ExportReport:
        items = source.scan()
        old_manifest = load_manifest(self.output_dir)
        old_items = old_manifest.get("items", {})
        new_manifest = {
            "schema_version": SCHEMA_VERSION,
            "exporter_version": EXPORTER_VERSION,
            "items": {},
        }
        report = ExportReport()
        csv_rows: list[dict[str, str]] = []
        seen_keys: set[str] = set()

        for item in sorted(items, key=lambda value: value.item_key):
            seen_keys.add(item.item_key)
            pdfs = item.pdf_attachments()
            if len(pdfs) == 0:
                report.errors.append(f"{item.item_key}: no PDF attachment")
                continue
            if len(pdfs) > 1:
                report.errors.append(f"{item.item_key}: multiple PDF attachments are not supported in 0.1.0")
                continue
            attachment = pdfs[0]
            if not attachment.source_path.exists():
                report.errors.append(f"{item.item_key}: source PDF is missing: {attachment.source_path}")
                continue

            pdf_rel, md_rel = output_relative_paths(item)
            pdf_out = self.output_dir / pdf_rel
            md_out = self.output_dir / md_rel
            metadata = render_metadata_markdown(item)
            metadata_fingerprint = sha256_text(metadata)
            stat = attachment.source_path.stat()
            manifest_entry = {
                "item_key": item.item_key,
                "attachment_key": attachment.attachment_key,
                "source_pdf_path": str(attachment.source_path),
                "output_pdf_relative_path": pdf_rel.as_posix(),
                "output_metadata_relative_path": md_rel.as_posix(),
                "source_file_size": stat.st_size,
                "source_modified_time": stat.st_mtime,
                "metadata_fingerprint": metadata_fingerprint,
                "exporter_schema_version": SCHEMA_VERSION,
                "exporter_version": EXPORTER_VERSION,
                "status": "active",
            }
            old_entry = old_items.get(item.item_key)
            pdf_changed = (
                old_entry is None
                or old_entry.get("source_file_size") != stat.st_size
                or old_entry.get("source_modified_time") != stat.st_mtime
                or old_entry.get("output_pdf_relative_path") != pdf_rel.as_posix()
                or not pdf_out.exists()
            )
            metadata_changed = (
                old_entry is None
                or old_entry.get("metadata_fingerprint") != metadata_fingerprint
                or old_entry.get("output_metadata_relative_path") != md_rel.as_posix()
                or not md_out.exists()
            )

            if old_entry is None:
                report.added += 1
            elif pdf_changed:
                report.updated_pdf += 1
            elif metadata_changed:
                report.updated_metadata += 1
            else:
                report.skipped += 1

            if not dry_run:
                if pdf_changed and self.copy_pdf:
                    pdf_out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(attachment.source_path, pdf_out)
                if metadata_changed and self.write_metadata:
                    atomic_write_text_if_changed(md_out, metadata)

            new_manifest["items"][item.item_key] = manifest_entry
            csv_rows.append(library_csv_row(item, pdf_rel, md_rel))

        for item_key, old_entry in sorted(old_items.items()):
            if item_key not in seen_keys:
                stale_entry = dict(old_entry)
                stale_entry["status"] = "stale"
                new_manifest["items"][item_key] = stale_entry
                report.stale += 1

        if not dry_run and self.write_index:
            atomic_write_text_if_changed(
                self.output_dir / "_Index" / "library.csv",
                render_library_csv(csv_rows),
            )
            atomic_write_text_if_changed(
                self.output_dir / "_Index" / "manifest.json",
                stable_json(new_manifest),
            )
        return report


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def render_metadata_markdown(item: LibraryItem) -> str:
    title = item.title or "Untitled"
    lines = [f"# {title}", ""]
    if item.authors:
        lines.append(f"Authors: {'; '.join(author.name for author in item.authors)}  ")
    else:
        lines.append("Authors: Unknown  ")
    lines.append(f"Year: {item.year or 'Unknown'}  ")
    if item.doi:
        lines.append(f"DOI: {item.doi}  ")
    lines.append(f"Zotero Item Key: {item.item_key}")
    lines.append("")
    if item.collections:
        lines.extend(["## Collections", ""])
        lines.extend(f"- {collection}" for collection in sorted(item.collections))
        lines.append("")
    if item.tags:
        lines.extend(["## Tags", ""])
        lines.extend(f"- {tag}" for tag in sorted(item.tags))
        lines.append("")
    if item.abstract:
        lines.extend(["## Abstract", "", item.abstract.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def library_csv_row(item: LibraryItem, pdf_rel: Path, md_rel: Path) -> dict[str, str]:
    return {
        "item_key": item.item_key,
        "title": item.title or "",
        "authors": MULTIVALUE_SEPARATOR.join(author.name for author in item.authors),
        "year": item.year or "",
        "doi": item.doi or "",
        "collections": MULTIVALUE_SEPARATOR.join(sorted(item.collections)),
        "tags": MULTIVALUE_SEPARATOR.join(sorted(item.tags)),
        "pdf_relative_path": pdf_rel.as_posix(),
        "metadata_relative_path": md_rel.as_posix(),
    }


def render_library_csv(rows: list[dict[str, str]]) -> str:
    fieldnames = [
        "item_key",
        "title",
        "authors",
        "year",
        "doi",
        "collections",
        "tags",
        "pdf_relative_path",
        "metadata_relative_path",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in sorted(rows, key=lambda value: value["item_key"]):
        writer.writerow(row)
    return buffer.getvalue()
