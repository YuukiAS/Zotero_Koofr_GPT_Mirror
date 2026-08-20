from __future__ import annotations

import argparse
import sys
from pathlib import Path

from zotero_gpt_mirror.config import load_config
from zotero_gpt_mirror.exporter import Exporter
from zotero_gpt_mirror.naming import normalize_output_path
from zotero_gpt_mirror.scan import summarize_items
from zotero_gpt_mirror.sources import FixtureSource, SourceUnavailableError, ZoteroLocalSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zotero-gpt-mirror")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export a local mirror.")
    add_common_options(export_parser)
    export_parser.add_argument("--dry-run", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate configuration and source readiness.")
    add_common_options(validate_parser)
    return parser


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", choices=["fixture", "zotero-local"], default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--fixture-dir", type=Path, default=None)
    parser.add_argument("--zotero-transport", choices=["auto", "direct", "windows-interop"], default=None)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)
    source_name = args.source or config.source
    output_raw = args.output_dir or config.output_dir
    output_dir = normalize_output_path(output_raw)
    repo_root = Path.cwd()

    try:
        source = make_source(source_name, args, config.zotero_local_api, config.zotero_transport)
        exporter = Exporter(
            output_dir=output_dir,
            repo_root=repo_root,
            raw_output_value=output_raw,
            copy_pdf=config.copy_pdf,
            write_metadata=config.write_metadata,
            write_index=config.write_index,
        )
        if args.command == "validate":
            print(summarize_items(source.scan()).human_summary())
            return 0
        report = exporter.export(source, dry_run=args.dry_run)
        print(report.human_summary(dry_run=args.dry_run))
        return 1 if report.errors else 0
    except (SourceUnavailableError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


def make_source(source_name: str, args: argparse.Namespace, zotero_api: str, zotero_transport: str):
    if source_name == "fixture":
        return FixtureSource(args.fixture_dir)
    if source_name == "zotero-local":
        return ZoteroLocalSource(
            api_url=zotero_api,
            transport_mode=args.zotero_transport or zotero_transport,
        )
    raise ValueError(f"Unknown source: {source_name}")
