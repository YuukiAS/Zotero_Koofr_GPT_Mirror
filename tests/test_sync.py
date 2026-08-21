from __future__ import annotations

from pathlib import Path

import pytest

from zotero_gpt_mirror.config import load_config
from zotero_gpt_mirror.exporter import Exporter
from zotero_gpt_mirror.sources.base import LibrarySource, SourceUnavailableError
from zotero_gpt_mirror.sources.fixture import FixtureSource
from zotero_gpt_mirror.sync import (
    RcloneConfig,
    RcloneResult,
    build_rclone_copy_args,
    collect_publish_snapshot,
    run_sync,
)


class FailingSource(LibrarySource):
    def scan(self):
        raise SourceUnavailableError("source failed")


class FakeRunner:
    def __init__(self, returncode: int = 0, stdout: str = "Transferred: 0 B", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def run(self, args: list[str]) -> RcloneResult:
        self.calls.append(args)
        return RcloneResult(args=args, returncode=self.returncode, stdout=self.stdout, stderr=self.stderr)


def test_exporter_failure_prevents_rclone_run(tmp_path: Path) -> None:
    runner = FakeRunner()
    with pytest.raises(SourceUnavailableError):
        run_sync(
            source=FailingSource(),
            exporter=Exporter(tmp_path / "mirror", Path.cwd()),
            rclone_config=RcloneConfig(),
            runner=runner,
        )
    assert runner.calls == []


def test_successful_export_runs_rclone_copy_to_default_target(tmp_path: Path) -> None:
    runner = FakeRunner()
    report = run_sync(
        source=FixtureSource(),
        exporter=Exporter(tmp_path / "mirror", Path.cwd()),
        rclone_config=RcloneConfig(),
        runner=runner,
    )
    assert report.ok
    assert report.snapshot.files == 28
    assert report.snapshot.pdf == 15
    assert report.snapshot.markdown == 12
    assert report.snapshot.csv == 1
    assert report.snapshot.manifest == 0
    assert runner.calls
    args = runner.calls[0]
    assert args[0:2] == ["rclone", "copy"]
    assert "sync" not in args
    assert args[3] == "gdrive:Zotero"


def test_rclone_copy_filters_publish_files_and_exclude_manifest(tmp_path: Path) -> None:
    args = build_rclone_copy_args(tmp_path / "mirror", RcloneConfig())
    joined = " ".join(args)
    assert "+ /Papers/**" in joined
    assert "+ /_Index/library.csv" in joined
    assert "- /_Index/manifest.json" in joined
    assert "- **" in joined


def test_dry_run_adds_rclone_dry_run_without_export_dry_run(tmp_path: Path) -> None:
    runner = FakeRunner()
    report = run_sync(
        source=FixtureSource(),
        exporter=Exporter(tmp_path / "mirror", Path.cwd()),
        rclone_config=RcloneConfig(),
        dry_run=True,
        runner=runner,
    )
    assert report.ok
    assert "--dry-run" in runner.calls[0]
    assert (tmp_path / "mirror" / "_Index" / "manifest.json").exists()


def test_rclone_nonzero_makes_sync_fail(tmp_path: Path) -> None:
    runner = FakeRunner(returncode=7, stderr="network failed")
    report = run_sync(
        source=FixtureSource(),
        exporter=Exporter(tmp_path / "mirror", Path.cwd()),
        rclone_config=RcloneConfig(),
        runner=runner,
    )
    assert not report.ok
    assert report.rclone_result is not None
    assert report.rclone_result.returncode == 7
    assert "network failed" in report.human_summary()


def test_rclone_failure_does_not_change_existing_manifest_on_retry(tmp_path: Path) -> None:
    output = tmp_path / "mirror"
    exporter = Exporter(output, Path.cwd())
    exporter.export(FixtureSource())
    before = (output / "_Index" / "manifest.json").read_text(encoding="utf-8")

    runner = FakeRunner(returncode=7, stderr="network failed")
    report = run_sync(
        source=FixtureSource(),
        exporter=exporter,
        rclone_config=RcloneConfig(),
        runner=runner,
    )
    after = (output / "_Index" / "manifest.json").read_text(encoding="utf-8")
    assert not report.ok
    assert after == before


def test_config_override_for_google_drive_sync(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[google_drive]
rclone_remote = "researchdrive"
folder = "Zotero"

[sync]
source = "fixture"
upload_manifest = true
""".lstrip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert config.rclone_remote == "researchdrive"
    assert config.google_drive_folder == "Zotero"
    assert config.sync_source == "fixture"
    assert config.upload_manifest is True


def test_upload_manifest_override_removes_manifest_exclude(tmp_path: Path) -> None:
    args = build_rclone_copy_args(tmp_path / "mirror", RcloneConfig(upload_manifest=True))
    joined = " ".join(args)
    assert "+ /_Index/manifest.json" in joined
    assert "- /_Index/manifest.json" not in joined


def test_publish_snapshot_can_include_manifest(tmp_path: Path) -> None:
    output = tmp_path / "mirror"
    Exporter(output, Path.cwd()).export(FixtureSource())
    snapshot = collect_publish_snapshot(output, upload_manifest=True)
    assert snapshot.files == 29
    assert snapshot.manifest == 1
