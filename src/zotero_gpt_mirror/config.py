from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from zotero_gpt_mirror.sources.zotero_local import DEFAULT_LOCAL_API


@dataclass(frozen=True)
class AppConfig:
    output_dir: str = "~/ZoteroGPTMirror"
    source: str = "fixture"
    copy_pdf: bool = True
    write_metadata: bool = True
    write_index: bool = True
    zotero_local_api: str = DEFAULT_LOCAL_API
    zotero_transport: str = "auto"


def load_config(path: Path | None) -> AppConfig:
    if path is None or not path.exists():
        return AppConfig()
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    mirror = data.get("mirror", {})
    export = data.get("export", {})
    zotero = data.get("zotero", {})
    return AppConfig(
        output_dir=str(mirror.get("output_dir", AppConfig.output_dir)),
        source=str(export.get("source", AppConfig.source)),
        copy_pdf=bool(export.get("copy_pdf", AppConfig.copy_pdf)),
        write_metadata=bool(export.get("write_metadata", AppConfig.write_metadata)),
        write_index=bool(export.get("write_index", AppConfig.write_index)),
        zotero_local_api=str(zotero.get("local_api", AppConfig.zotero_local_api)),
        zotero_transport=str(zotero.get("transport", AppConfig.zotero_transport)),
    )
