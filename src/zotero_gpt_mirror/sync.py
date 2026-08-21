from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from zotero_gpt_mirror.exporter import ExportReport, Exporter
from zotero_gpt_mirror.sources.base import LibrarySource


@dataclass(frozen=True)
class RcloneConfig:
    remote: str = "gdrive"
    folder: str = "Zotero"
    upload_manifest: bool = False


@dataclass(frozen=True)
class RcloneResult:
    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class PublishSnapshot:
    files: int = 0
    bytes: int = 0
    pdf: int = 0
    markdown: int = 0
    csv: int = 0
    manifest: int = 0


class RcloneRunner(Protocol):
    def run(self, args: list[str]) -> RcloneResult:
        ...


class SubprocessRcloneRunner:
    def run(self, args: list[str]) -> RcloneResult:
        try:
            completed = subprocess.run(args, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            return RcloneResult(args=args, returncode=127, stderr=str(exc))
        return RcloneResult(
            args=args,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


@dataclass(frozen=True)
class SyncReport:
    export_report: ExportReport
    rclone_result: RcloneResult | None
    target: str
    snapshot: PublishSnapshot
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        return not self.export_report.errors and self.rclone_result is not None and self.rclone_result.returncode == 0

    def human_summary(self) -> str:
        lines = ["Zotero export:"]
        lines.extend(f"  {line}" for line in self.export_report.human_summary().splitlines())
        lines.append("")
        lines.append("Google Drive:")
        lines.append(f"  target: {self.target}")
        lines.append(f"  dry-run: {'yes' if self.dry_run else 'no'}")
        lines.append(f"  planned files: {self.snapshot.files}")
        lines.append(f"  planned bytes: {self.snapshot.bytes}")
        lines.append(f"  planned PDFs: {self.snapshot.pdf}")
        lines.append(f"  planned Markdown: {self.snapshot.markdown}")
        lines.append(f"  planned CSV: {self.snapshot.csv}")
        lines.append(f"  planned manifest: {self.snapshot.manifest}")
        if self.rclone_result is None:
            lines.append("  rclone: not run because export failed")
            return "\n".join(lines)

        lines.append(f"  command: {shlex.join(self.rclone_result.args)}")
        lines.append(f"  exit code: {self.rclone_result.returncode}")
        stdout = self.rclone_result.stdout.strip()
        stderr = self.rclone_result.stderr.strip()
        if stdout:
            lines.append("  stdout:")
            lines.extend(f"    {line}" for line in stdout.splitlines())
        if stderr:
            lines.append("  stderr:")
            lines.extend(f"    {line}" for line in stderr.splitlines())
        return "\n".join(lines)


def run_sync(
    *,
    source: LibrarySource,
    exporter: Exporter,
    rclone_config: RcloneConfig,
    dry_run: bool = False,
    runner: RcloneRunner | None = None,
) -> SyncReport:
    export_report = exporter.export(source, dry_run=False)
    target = rclone_target(rclone_config)
    snapshot = collect_publish_snapshot(exporter.output_dir, upload_manifest=rclone_config.upload_manifest)
    if export_report.errors:
        return SyncReport(
            export_report=export_report,
            rclone_result=None,
            target=target,
            snapshot=snapshot,
            dry_run=dry_run,
        )

    active_runner = runner or SubprocessRcloneRunner()
    args = build_rclone_copy_args(exporter.output_dir, rclone_config, dry_run=dry_run)
    rclone_result = active_runner.run(args)
    return SyncReport(
        export_report=export_report,
        rclone_result=rclone_result,
        target=target,
        snapshot=snapshot,
        dry_run=dry_run,
    )


def rclone_target(config: RcloneConfig) -> str:
    remote = config.remote.rstrip(":")
    folder = config.folder.strip().strip("/")
    if not remote:
        raise ValueError("Google Drive rclone remote must not be empty.")
    if not folder:
        raise ValueError("Google Drive folder must not be empty.")
    return f"{remote}:{folder}"


def build_rclone_copy_args(source_dir: Path, config: RcloneConfig, dry_run: bool = False) -> list[str]:
    args = [
        "rclone",
        "copy",
        str(source_dir),
        rclone_target(config),
        "--filter",
        "+ /Papers/**",
        "--filter",
        "+ /_Index/",
        "--filter",
        "+ /_Index/library.csv",
    ]
    if config.upload_manifest:
        args.extend(["--filter", "+ /_Index/manifest.json"])
    else:
        args.extend(["--filter", "- /_Index/manifest.json"])
    args.extend(
        [
            "--filter",
            "- **",
            "--stats-one-line",
            "--stats",
            "30s",
        ]
    )
    if dry_run:
        args.append("--dry-run")
    return args


def collect_publish_snapshot(source_dir: Path, upload_manifest: bool = False) -> PublishSnapshot:
    files = 0
    total_bytes = 0
    pdf = 0
    markdown = 0
    csv = 0
    manifest = 0

    for path in iter_publish_files(source_dir, upload_manifest=upload_manifest):
        files += 1
        total_bytes += path.stat().st_size
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            pdf += 1
        elif suffix == ".md":
            markdown += 1
        elif suffix == ".csv":
            csv += 1
        if path.name == "manifest.json" and path.parent.name == "_Index":
            manifest += 1

    return PublishSnapshot(files=files, bytes=total_bytes, pdf=pdf, markdown=markdown, csv=csv, manifest=manifest)


def iter_publish_files(source_dir: Path, upload_manifest: bool = False):
    papers = source_dir / "Papers"
    if papers.exists():
        yield from (path for path in sorted(papers.rglob("*")) if path.is_file())

    library_csv = source_dir / "_Index" / "library.csv"
    if library_csv.exists():
        yield library_csv

    manifest = source_dir / "_Index" / "manifest.json"
    if upload_manifest and manifest.exists():
        yield manifest
