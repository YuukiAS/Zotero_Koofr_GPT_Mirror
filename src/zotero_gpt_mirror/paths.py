from __future__ import annotations

import re
import subprocess
import urllib.parse
from pathlib import Path


class PathConversionError(RuntimeError):
    pass


def file_url_to_windows_path(file_url: str) -> str:
    parsed = urllib.parse.urlparse(file_url.strip().strip('"'))
    if parsed.scheme != "file":
        raise PathConversionError(f"Expected file:// URL, got: {file_url}")
    decoded_path = urllib.parse.unquote(parsed.path)
    if parsed.netloc:
        return "\\\\" + parsed.netloc + decoded_path.replace("/", "\\")
    if re.match(r"^/[A-Za-z]:/", decoded_path):
        decoded_path = decoded_path[1:]
    return decoded_path.replace("/", "\\")


def windows_path_to_wsl_path(windows_path: str) -> Path:
    completed = subprocess.run(
        ["wslpath", "-u", windows_path],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise PathConversionError(completed.stderr.strip() or f"wslpath failed for {windows_path}")
    return Path(completed.stdout.strip())


def file_url_to_wsl_path(file_url: str) -> Path:
    return windows_path_to_wsl_path(file_url_to_windows_path(file_url))
