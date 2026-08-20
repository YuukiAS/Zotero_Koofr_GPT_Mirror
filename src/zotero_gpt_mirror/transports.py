from __future__ import annotations

import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class TransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: str
    headers: dict[str, str]


class LocalApiTransport(Protocol):
    def get(self, path: str) -> HttpResponse:
        pass


class DirectHttpTransport:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(self, path: str) -> HttpResponse:
        url = join_url(self.base_url, path)
        request = urllib.request.Request(url, headers={"Zotero-API-Version": "3"})
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                return HttpResponse(
                    status=response.status,
                    body=response.read().decode("utf-8"),
                    headers={key.lower(): value for key, value in response.headers.items()},
                )
        except urllib.error.HTTPError as exc:
            return HttpResponse(
                status=exc.code,
                body=exc.read().decode("utf-8", errors="replace"),
                headers={key.lower(): value for key, value in exc.headers.items()},
            )
        except OSError as exc:
            raise TransportError(str(exc)) from exc


class WindowsInteropTransport:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        curl_exe: str = "curl.exe",
        cmd_exe: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds
        self.curl_exe = resolve_windows_curl(curl_exe) or curl_exe
        self.cmd_exe = cmd_exe or resolve_windows_cmd()
        self.wsl_interop = resolve_wsl_interop()

    def available(self) -> bool:
        return Path(self.curl_exe).is_file() or shutil.which(self.curl_exe) is not None or bool(self.cmd_exe)

    def get(self, path: str) -> HttpResponse:
        if not self.available():
            raise TransportError("Windows interop cmd.exe/curl.exe is not available from WSL.")
        url = join_url(self.base_url, path)
        curl_args = [
            self.curl_exe,
            "-sS",
            "--noproxy",
            "127.0.0.1,localhost",
            "-H",
            "Zotero-API-Version: 3",
            "-D",
            "-",
            url,
        ]
        command = curl_args
        env = os.environ.copy()
        if self.wsl_interop and "WSL_INTEROP" not in env:
            env["WSL_INTEROP"] = self.wsl_interop
        cwd = "/mnt/c/Windows/System32" if Path("/mnt/c/Windows/System32").is_dir() else None
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransportError(f"{self.curl_exe} timed out for {url}") from exc
        if completed.returncode != 0 and self.cmd_exe:
            cmd_command = [self.cmd_exe, "/d", "/c", windows_command_line(curl_args)]
            try:
                completed = subprocess.run(
                    cmd_command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    env=env,
                    cwd=cwd,
                )
            except subprocess.TimeoutExpired as exc:
                raise TransportError(f"{self.cmd_exe} timed out for {url}") from exc
        if completed.returncode != 0:
            raise TransportError(completed.stderr.strip() or f"{self.curl_exe} failed")
        return parse_curl_response(completed.stdout)


def resolve_windows_cmd() -> str | None:
    discovered = shutil.which("cmd.exe")
    if discovered:
        return discovered
    system32_cmd = Path("/mnt/c/Windows/System32/cmd.exe")
    if system32_cmd.is_file():
        return str(system32_cmd)
    return None


def resolve_windows_curl(curl_exe: str) -> str | None:
    discovered = shutil.which(curl_exe)
    if discovered:
        return discovered
    system32_curl = Path("/mnt/c/Windows/System32/curl.exe")
    if system32_curl.is_file():
        return str(system32_curl)
    return None


def windows_command_line(args: list[str]) -> str:
    return " ".join(shlex.quote(arg).replace("'", '"') for arg in args)


def resolve_wsl_interop() -> str | None:
    current = os.environ.get("WSL_INTEROP")
    if current:
        return current
    run_wsl = Path("/run/WSL")
    if not run_wsl.is_dir():
        return None
    sockets = sorted(
        [path for path in run_wsl.glob("*_interop") if path.exists()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return str(sockets[0]) if sockets else None


class AutoTransport:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self.direct = DirectHttpTransport(base_url, timeout_seconds)
        self.windows_interop = WindowsInteropTransport(base_url, timeout_seconds)
        self.selected: str | None = None

    def get(self, path: str) -> HttpResponse:
        if self.selected == "direct":
            return self.direct.get(path)
        if self.selected == "windows-interop":
            return self.windows_interop.get(path)
        direct_error: TransportError | None = None
        try:
            response = self.direct.get(path)
            self.selected = "direct"
            return response
        except TransportError as exc:
            direct_error = exc
        try:
            response = self.windows_interop.get(path)
            self.selected = "windows-interop"
            return response
        except TransportError as exc:
            raise TransportError(
                f"Direct localhost failed: {direct_error}. Windows interop failed: {exc}"
            ) from exc


def join_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urllib.parse.urljoin(base_url, path.lstrip("/"))


def parse_curl_response(raw: str) -> HttpResponse:
    header_text, separator, body = raw.partition("\r\n\r\n")
    if not separator:
        header_text, separator, body = raw.partition("\n\n")
    if not separator:
        raise TransportError("Could not parse curl.exe HTTP response.")
    lines = header_text.replace("\r\n", "\n").split("\n")
    status_line = lines[0].strip()
    parts = status_line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        raise TransportError(f"Could not parse HTTP status line: {status_line}")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return HttpResponse(status=int(parts[1]), body=body, headers=headers)
