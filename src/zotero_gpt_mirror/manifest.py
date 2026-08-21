from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
EXPORTER_VERSION = "0.3.0"


def load_manifest(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "_Index" / "manifest.json"
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "exporter_version": EXPORTER_VERSION, "items": {}}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def stable_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atomic_write_text_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temp_path, path)
    return True
