from pathlib import Path

from zotero_gpt_mirror.cli import main
from zotero_gpt_mirror.sources.base import SourceUnavailableError
from zotero_gpt_mirror.sources.zotero_local import ZoteroLocalSource


def test_cli_dry_run_fixture_does_not_create_output(tmp_path: Path, capsys) -> None:
    output = tmp_path / "mirror"
    code = main(["export", "--source", "fixture", "--output-dir", str(output), "--dry-run"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Would add: 11" in captured.out
    assert not output.exists()


def test_cli_rejects_source_tree_output(tmp_path: Path, capsys) -> None:
    code = main(["export", "--source", "fixture", "--output-dir", str(Path.cwd())])
    captured = capsys.readouterr()
    assert code == 2
    assert "project source tree" in captured.err


def test_zotero_local_unavailable_error_is_friendly() -> None:
    source = ZoteroLocalSource("http://127.0.0.1:9/api/", timeout_seconds=0.1)
    try:
        source.scan()
    except SourceUnavailableError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected SourceUnavailableError")
    assert "Zotero Local API is not available" in message
    assert "Use `--source fixture`" in message
    assert "Traceback" not in message
