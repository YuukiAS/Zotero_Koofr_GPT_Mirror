from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path, PureWindowsPath

from zotero_gpt_mirror.models import LibraryItem

INVALID_WINDOWS_CHARS = '<>:"/\\|?*'
RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
MAX_FILENAME_CHARS = 180


def sanitize_filename_segment(value: str | None, fallback: str = "Unknown") -> str:
    text = unicodedata.normalize("NFC", value or "").strip()
    translation = str.maketrans({char: " " for char in INVALID_WINDOWS_CHARS})
    text = text.translate(translation)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = fallback
    stem = text.split(".", 1)[0].upper()
    if stem in RESERVED_WINDOWS_NAMES:
        text = f"{text}_"
    return text


def author_label(item: LibraryItem) -> str:
    if not item.authors:
        return "Unknown Author"
    first = item.authors[0].name.strip()
    if not first:
        label = "Unknown Author"
    elif " " in first:
        label = first.split()[-1]
    else:
        label = first
    if len(item.authors) > 1:
        label = f"{label} et al"
    return sanitize_filename_segment(label, "Unknown Author")


def year_dir(year: str | None) -> str:
    return sanitize_filename_segment(year, "Unknown-Year")


def mirror_stem(item: LibraryItem) -> str:
    key = sanitize_filename_segment(item.item_key, "NOITEMKEY")
    author = author_label(item)
    title = sanitize_filename_segment(item.title, "Untitled")
    suffix = f" [{key}]"
    prefix = f"{author} - "
    available_title = MAX_FILENAME_CHARS - len(".pdf") - len(prefix) - len(suffix)
    if available_title < 16:
        available_title = 16
    if len(title) > available_title:
        title = title[:available_title].rstrip(" .")
    return sanitize_filename_segment(f"{prefix}{title}{suffix}", key)


def mirror_filename(item: LibraryItem, extension: str) -> str:
    return f"{mirror_stem(item)}{extension}"


def output_relative_paths(item: LibraryItem) -> tuple[Path, Path]:
    pdf_name = mirror_filename(item, ".pdf")
    md_name = mirror_filename(item, ".md")
    paper_dir = Path("Papers") / year_dir(item.year)
    return paper_dir / pdf_name, paper_dir / md_name


def is_windows_drive_root(raw: str) -> bool:
    win = PureWindowsPath(raw)
    return bool(win.drive) and str(win).replace("/", "\\").rstrip("\\") == win.drive


def is_windows_users_root(raw: str) -> bool:
    win = PureWindowsPath(raw)
    parts = [part.lower() for part in win.parts]
    return len(parts) == 2 and parts[0].endswith(":\\") and parts[1] == "users"


def normalize_output_path(raw: str | os.PathLike[str]) -> Path:
    text = str(raw)
    win = PureWindowsPath(text)
    if os.name != "nt" and win.drive:
        drive = win.drive.rstrip(":").lower()
        return Path("/mnt") / drive / Path(*win.parts[1:])
    return Path(text).expanduser()


def validate_output_dir(output_dir: Path, raw_value: str | os.PathLike[str], repo_root: Path) -> None:
    raw = str(raw_value)
    if is_windows_drive_root(raw) or is_windows_users_root(raw):
        raise ValueError(f"Refusing dangerous mirror output_dir: {raw}")
    resolved = output_dir.resolve()
    repo = repo_root.resolve()
    if resolved == repo or repo in resolved.parents:
        raise ValueError(f"Refusing to place mirror output inside the project source tree: {resolved}")
    if resolved.parent == resolved:
        raise ValueError(f"Refusing filesystem root as mirror output_dir: {resolved}")
