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
from zotero_gpt_mirror.models import LibraryItem, PdfAttachment
from zotero_gpt_mirror.naming import (
    attachment_pdf_relative_path,
    item_metadata_relative_path,
    item_primary_pdf_relative_path,
    validate_output_dir,
)
from zotero_gpt_mirror.sources.base import LibrarySource

MULTIVALUE_SEPARATOR = " | "


@dataclass
class ExportReport:
    added: int = 0
    updated_metadata: int = 0
    updated_pdf: int = 0
    skipped: int = 0
    stale: int = 0
    no_pdf_attachment: int = 0
    missing_local_attachment: int = 0
    multiple_pdf_attachments: int = 0
    ambiguous_primary_items: int = 0
    duplicate_pdfs_suppressed: int = 0
    errors: list[str] = field(default_factory=list)

    def human_summary(self, dry_run: bool = False) -> str:
        prefix = "Would " if dry_run else ""
        lines = [
            f"{prefix}add: {self.added}",
            f"{prefix}update metadata: {self.updated_metadata}",
            f"{prefix}update PDF: {self.updated_pdf}",
            f"{prefix}skip: {self.skipped}",
            f"{prefix}mark stale: {self.stale}",
            f"No PDF attachment: {self.no_pdf_attachment}",
            f"Missing local attachment: {self.missing_local_attachment}",
            f"Items with multiple PDFs: {self.multiple_pdf_attachments}",
            f"Ambiguous primary items: {self.ambiguous_primary_items}",
            f"Exact duplicate PDFs suppressed: {self.duplicate_pdfs_suppressed}",
        ]
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
            lines.extend(f"- {error}" for error in self.errors)
        return "\n".join(lines)


@dataclass(frozen=True)
class AttachmentPlan:
    attachment: PdfAttachment
    role: str
    output_rel: Path | None
    local_status: str
    duplicate_of: str | None = None
    source_hash: str | None = None


@dataclass(frozen=True)
class ItemPlan:
    item: LibraryItem
    attachments: tuple[AttachmentPlan, ...]
    primary_status: str


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
            plan = build_item_plan(item)
            pdfs = plan.attachments
            if len(pdfs) == 0:
                report.no_pdf_attachment += 1
                continue
            if len(pdfs) > 1:
                report.multiple_pdf_attachments += 1
            if plan.primary_status == "ambiguous":
                report.ambiguous_primary_items += 1
            report.duplicate_pdfs_suppressed += sum(1 for attachment in pdfs if attachment.duplicate_of)

            md_rel = item_metadata_relative_path(item)
            md_out = self.output_dir / md_rel
            metadata = render_metadata_markdown(item, plan)
            metadata_fingerprint = sha256_text(metadata)
            old_entry = old_items.get(item.item_key, {})
            old_attachments = old_attachments_by_key(old_entry)
            metadata_changed = (
                old_entry.get("bibliographic_metadata_fingerprint") != metadata_fingerprint
                or old_entry.get("output_metadata_relative_path") != md_rel.as_posix()
                or not md_out.exists()
            )
            if not dry_run and metadata_changed and self.write_metadata:
                atomic_write_text_if_changed(md_out, metadata)

            attachment_entries = []
            copied_or_changed = False
            exportable_seen = False
            for attachment_plan in pdfs:
                attachment = attachment_plan.attachment
                old_attachment = old_attachments.get(attachment.attachment_key, {})
                attachment_entry = manifest_attachment_entry(attachment_plan)
                attachment_entries.append(attachment_entry)
                if attachment_plan.local_status != "available":
                    report.missing_local_attachment += 1
                    continue
                if attachment_plan.duplicate_of:
                    continue
                if attachment_plan.output_rel is None or attachment.source_path is None:
                    report.missing_local_attachment += 1
                    continue
                exportable_seen = True
                pdf_out = self.output_dir / attachment_plan.output_rel
                pdf_changed = (
                    old_attachment.get("source_file_size") != attachment_entry.get("source_file_size")
                    or old_attachment.get("source_modified_time") != attachment_entry.get("source_modified_time")
                    or old_attachment.get("output_pdf_relative_path") != attachment_plan.output_rel.as_posix()
                    or old_attachment.get("source_hash") != attachment_plan.source_hash
                    or not pdf_out.exists()
                )
                if pdf_changed:
                    copied_or_changed = True
                    if not dry_run and self.copy_pdf:
                        pdf_out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(attachment.source_path, pdf_out)

            manifest_entry = {
                "item_key": item.item_key,
                "output_metadata_relative_path": md_rel.as_posix(),
                "bibliographic_metadata_fingerprint": metadata_fingerprint,
                "primary_status": plan.primary_status,
                "attachments": attachment_entries,
                "exporter_schema_version": SCHEMA_VERSION,
                "exporter_version": EXPORTER_VERSION,
                "status": "active",
            }

            if old_entry == {}:
                report.added += 1
            elif copied_or_changed:
                report.updated_pdf += 1
            elif metadata_changed:
                report.updated_metadata += 1
            else:
                report.skipped += 1

            new_manifest["items"][item.item_key] = manifest_entry
            if exportable_seen or pdfs:
                csv_rows.append(library_csv_row(item, plan, md_rel))

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


def render_metadata_markdown(item: LibraryItem, plan: ItemPlan | None = None) -> str:
    title = item.title or "Untitled"
    lines = [f"# {title}", ""]
    if item.authors:
        lines.append(f"Authors: {'; '.join(author.name for author in item.authors)}  ")
    else:
        lines.append("Authors: Unknown  ")
    lines.append(f"Year: {item.year or 'Unknown'}  ")
    if item.doi:
        lines.append(f"DOI: {item.doi}  ")
    if item.url:
        lines.append(f"URL: {item.url}  ")
    lines.append(f"Zotero Item Key: {item.item_key}")
    if plan:
        lines.append(f"Primary Status: {plan.primary_status}")
    lines.append("")
    if plan:
        lines.extend(["## PDF Attachments", ""])
        for attachment_plan in plan.attachments:
            attachment = attachment_plan.attachment
            lines.append(f"- {attachment_plan.role.replace('_', ' ').title()}")
            if attachment.title:
                lines.append(f"  - Title: {attachment.title}")
            lines.append(f"  - Original Filename: {attachment.filename}")
            lines.append(f"  - Zotero Attachment Key: {attachment.attachment_key}")
            if attachment_plan.output_rel:
                lines.append(f"  - File: `{attachment_plan.output_rel.name}`")
            lines.append(f"  - Local Status: {attachment_plan.local_status}")
            if attachment_plan.duplicate_of:
                lines.append(f"  - Duplicate Of: {attachment_plan.duplicate_of}")
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


def library_csv_row(item: LibraryItem, plan: ItemPlan, md_rel: Path) -> dict[str, str]:
    exported_paths = [
        attachment.output_rel.as_posix()
        for attachment in plan.attachments
        if attachment.output_rel is not None and attachment.local_status == "available" and not attachment.duplicate_of
    ]
    primary_paths = [
        attachment.output_rel.as_posix()
        for attachment in plan.attachments
        if attachment.output_rel is not None and attachment.role == "primary" and not attachment.duplicate_of
    ]
    statuses = [
        f"{attachment.attachment.attachment_key}:{attachment.role}:{attachment.local_status}"
        + (f":duplicate_of={attachment.duplicate_of}" if attachment.duplicate_of else "")
        for attachment in plan.attachments
    ]
    return {
        "item_key": item.item_key,
        "title": item.title or "",
        "authors": MULTIVALUE_SEPARATOR.join(author.name for author in item.authors),
        "year": item.year or "",
        "doi": item.doi or "",
        "url": item.url or "",
        "pdf_count": str(len(exported_paths)),
        "primary_pdf": primary_paths[0] if len(primary_paths) == 1 else "",
        "pdf_paths": MULTIVALUE_SEPARATOR.join(exported_paths),
        "attachment_status": MULTIVALUE_SEPARATOR.join(statuses),
        "collections": MULTIVALUE_SEPARATOR.join(sorted(item.collections)),
        "tags": MULTIVALUE_SEPARATOR.join(sorted(item.tags)),
        "metadata_relative_path": md_rel.as_posix(),
    }


def render_library_csv(rows: list[dict[str, str]]) -> str:
    fieldnames = [
        "item_key",
        "title",
        "authors",
        "year",
        "doi",
        "url",
        "pdf_count",
        "primary_pdf",
        "pdf_paths",
        "attachment_status",
        "collections",
        "tags",
        "metadata_relative_path",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in sorted(rows, key=lambda value: value["item_key"]):
        writer.writerow(row)
    return buffer.getvalue()


def old_attachments_by_key(old_entry: dict) -> dict[str, dict]:
    if "attachments" in old_entry:
        return {
            attachment.get("attachment_key"): attachment
            for attachment in old_entry.get("attachments", [])
            if attachment.get("attachment_key")
        }
    if old_entry.get("attachment_key"):
        return {old_entry["attachment_key"]: old_entry}
    return {}


def build_item_plan(item: LibraryItem) -> ItemPlan:
    pdfs = item.pdf_attachments()
    roles, primary_status = classify_attachment_roles(pdfs)
    seen_hashes: dict[str, str] = {}
    seen_hash_outputs: dict[str, Path] = {}
    plans = []
    for attachment, role in zip(pdfs, roles, strict=True):
        local_status = "available" if attachment.source_path and attachment.source_path.exists() else "missing_local_attachment"
        source_hash = None
        duplicate_of = None
        output_rel = None
        if local_status == "available":
            if role == "primary":
                output_rel = item_primary_pdf_relative_path(item)
            else:
                output_rel = attachment_pdf_relative_path(item, attachment)
        if local_status == "available" and len(pdfs) > 1 and attachment.source_path is not None:
            source_hash = sha256_file(attachment.source_path)
            duplicate_of = seen_hashes.get(source_hash)
            if duplicate_of is None:
                seen_hashes[source_hash] = attachment.attachment_key
                if output_rel is not None:
                    seen_hash_outputs[source_hash] = output_rel
            else:
                output_rel = seen_hash_outputs.get(source_hash, output_rel)
        plans.append(
            AttachmentPlan(
                attachment=attachment,
                role=role,
                output_rel=output_rel,
                local_status=local_status,
                duplicate_of=duplicate_of,
                source_hash=source_hash,
            )
        )
    return ItemPlan(item=item, attachments=tuple(plans), primary_status=primary_status)


def classify_attachment_roles(pdfs: tuple[PdfAttachment, ...]) -> tuple[list[str], str]:
    if not pdfs:
        return [], "none"
    if len(pdfs) == 1:
        return ["primary"], "single"
    initial = [classify_attachment_role(attachment) for attachment in pdfs]
    primary_candidates = [index for index, role in enumerate(initial) if role == "primary_candidate"]
    if len(primary_candidates) == 1:
        roles = ["primary" if index == primary_candidates[0] else role for index, role in enumerate(initial)]
        roles = ["additional" if role == "primary_candidate" else role for role in roles]
        return roles, "identified"
    return ["additional" if role == "primary_candidate" else role for role in initial], "ambiguous"


def classify_attachment_role(attachment: PdfAttachment) -> str:
    text = f"{attachment.title or ''} {attachment.filename or ''}".lower()
    normalized = text.replace("_", " ").replace("-", " ")
    if any(value in normalized for value in ["appendix", "附录"]):
        return "appendix"
    if any(value in normalized for value in ["supporting information", "supplementary", "supplement", "suppinfo", " supp", "mmc", "moesm"]):
        return "supplement"
    if "protocol" in normalized:
        return "protocol"
    if "questionnaire" in normalized:
        return "questionnaire"
    if any(value in normalized for value in ["accepted", "publisher", "manuscript", "author copy", "已接受", "已提交"]):
        return "alternate_version"
    title = (attachment.title or "").strip().lower()
    if title in {"pdf", "full text", "full text pdf"} or ".full" in normalized:
        return "primary_candidate"
    return "additional"


def manifest_attachment_entry(plan: AttachmentPlan) -> dict[str, object]:
    attachment = plan.attachment
    source_path = attachment.source_path
    stat = source_path.stat() if source_path and source_path.exists() else None
    return {
        "attachment_key": attachment.attachment_key,
        "title": attachment.title,
        "original_filename": attachment.filename,
        "role": plan.role,
        "source_pdf_path": str(source_path) if source_path else "",
        "output_pdf_relative_path": plan.output_rel.as_posix() if plan.output_rel else "",
        "source_file_size": stat.st_size if stat else None,
        "source_modified_time": stat.st_mtime if stat else None,
        "source_hash": plan.source_hash,
        "duplicate_of": plan.duplicate_of,
        "local_status": plan.local_status,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
