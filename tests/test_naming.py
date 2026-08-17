from pathlib import Path

import pytest

from zotero_gpt_mirror.models import Author, LibraryItem
from zotero_gpt_mirror.naming import (
    MAX_FILENAME_CHARS,
    mirror_filename,
    output_relative_paths,
    sanitize_filename_segment,
    validate_output_dir,
)


def test_windows_invalid_characters_are_removed() -> None:
    value = 'A:B/C?D*E"F<G>H|'
    sanitized = sanitize_filename_segment(value)
    for char in '<>:"/\\|?*':
        assert char not in sanitized
    assert sanitized == "A B C D E F G H"


def test_reserved_windows_name_is_escaped() -> None:
    assert sanitize_filename_segment("CON") == "CON_"
    assert sanitize_filename_segment("LPT1.txt") == "LPT1.txt_"


def test_long_filename_preserves_item_key_suffix() -> None:
    item = LibraryItem(
        item_key="LONGKEY1",
        item_type="journalArticle",
        title="x" * 400,
        authors=(Author("Alice Smith"),),
        year="2026",
    )
    filename = mirror_filename(item, ".pdf")
    assert len(filename) <= MAX_FILENAME_CHARS
    assert filename.endswith("[LONGKEY1].pdf")


def test_unicode_title_and_author_survive() -> None:
    item = LibraryItem(
        item_key="UNICODE8",
        item_type="journalArticle",
        title="中文标题",
        authors=(Author("陈 小明"),),
        year="2026",
    )
    pdf_rel, _ = output_relative_paths(item)
    assert "小明 - 中文标题 [UNICODE8].pdf" in pdf_rel.as_posix()


def test_duplicate_titles_are_distinguished_by_item_key() -> None:
    first = LibraryItem("KEYA", "journalArticle", title="Same", authors=(Author("Alice Smith"),), year="2026")
    second = LibraryItem("KEYB", "journalArticle", title="Same", authors=(Author("Alice Smith"),), year="2026")
    assert output_relative_paths(first)[0] != output_relative_paths(second)[0]


def test_pdf_and_metadata_use_same_stem_for_long_titles() -> None:
    item = LibraryItem(
        item_key="LONGKEY2",
        item_type="journalArticle",
        title="x" * 400,
        authors=(Author("Alice Smith"),),
        year="2026",
    )
    pdf_rel, md_rel = output_relative_paths(item)
    assert pdf_rel.with_suffix("").name == md_rel.with_suffix("").name


def test_dangerous_output_dirs_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        validate_output_dir(Path("/mnt/c"), "C:\\", tmp_path)
    with pytest.raises(ValueError):
        validate_output_dir(Path("/mnt/c/Users"), "C:\\Users", tmp_path)
    with pytest.raises(ValueError):
        validate_output_dir(tmp_path / "mirror", tmp_path / "mirror", tmp_path)
