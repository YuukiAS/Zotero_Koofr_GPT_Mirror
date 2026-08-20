from __future__ import annotations

from dataclasses import dataclass

from zotero_gpt_mirror.exporter import build_item_plan
from zotero_gpt_mirror.models import LibraryItem


@dataclass(frozen=True)
class ScanSummary:
    bibliographic_items: int
    items_with_one_pdf: int
    items_with_multiple_pdfs: int
    exportable_pdf_attachments: int
    no_pdf_attachment: int
    missing_local_attachment: int
    ambiguous_primary_items: int
    duplicate_pdfs_suppressed: int
    collections: int
    tags: int

    def human_summary(self) -> str:
        return "\n".join(
            [
                f"Bibliographic items: {self.bibliographic_items}",
                f"Items with one PDF: {self.items_with_one_pdf}",
                f"Items with multiple PDFs: {self.items_with_multiple_pdfs}",
                f"PDF attachments exportable: {self.exportable_pdf_attachments}",
                f"No PDF attachment: {self.no_pdf_attachment}",
                f"Missing local PDF attachments: {self.missing_local_attachment}",
                f"Ambiguous primary items: {self.ambiguous_primary_items}",
                f"Exact duplicate PDFs suppressed: {self.duplicate_pdfs_suppressed}",
                f"Collections: {self.collections}",
                f"Tags: {self.tags}",
            ]
        )


def summarize_items(items: list[LibraryItem]) -> ScanSummary:
    items_with_one_pdf = 0
    items_with_multiple_pdfs = 0
    exportable_pdf_attachments = 0
    no_pdf_attachment = 0
    missing_local_attachment = 0
    ambiguous_primary_items = 0
    duplicate_pdfs_suppressed = 0
    collections = set()
    tags = set()

    for item in items:
        collections.update(value for value in item.collections if value)
        tags.update(value for value in item.tags if value)
        pdfs = item.pdf_attachments()
        if not pdfs:
            no_pdf_attachment += 1
        else:
            if len(pdfs) == 1:
                items_with_one_pdf += 1
            else:
                items_with_multiple_pdfs += 1
            plan = build_item_plan(item)
            if plan.primary_status == "ambiguous":
                ambiguous_primary_items += 1
            for attachment in plan.attachments:
                if attachment.local_status == "available":
                    if attachment.duplicate_of:
                        duplicate_pdfs_suppressed += 1
                    else:
                        exportable_pdf_attachments += 1
                else:
                    missing_local_attachment += 1

    return ScanSummary(
        bibliographic_items=len(items),
        items_with_one_pdf=items_with_one_pdf,
        items_with_multiple_pdfs=items_with_multiple_pdfs,
        exportable_pdf_attachments=exportable_pdf_attachments,
        no_pdf_attachment=no_pdf_attachment,
        missing_local_attachment=missing_local_attachment,
        ambiguous_primary_items=ambiguous_primary_items,
        duplicate_pdfs_suppressed=duplicate_pdfs_suppressed,
        collections=len(collections),
        tags=len(tags),
    )
