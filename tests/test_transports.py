from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from zotero_gpt_mirror.transports import DirectHttpTransport, WindowsInteropTransport, parse_curl_response


def test_parse_curl_response_reads_status_headers_and_body() -> None:
    response = parse_curl_response("HTTP/1.1 200 OK\r\nLink: <next>; rel=\"next\"\r\n\r\n[]")
    assert response.status == 200
    assert response.headers["link"] == '<next>; rel="next"'
    assert response.body == "[]"


def test_direct_http_transport_gets_json_and_sends_api_version() -> None:
    seen_headers = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen_headers["zotero"] = self.headers.get("Zotero-API-Version")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"[]")

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        transport = DirectHttpTransport(f"http://127.0.0.1:{server.server_port}/api/")
        response = transport.get("users/0/items")
    finally:
        server.shutdown()
    assert response.status == 200
    assert response.body == "[]"
    assert seen_headers["zotero"] == "3"


def test_windows_interop_transport_invokes_curl_exe(monkeypatch) -> None:
    monkeypatch.setattr("zotero_gpt_mirror.transports.shutil.which", lambda name: None)
    monkeypatch.setattr("zotero_gpt_mirror.transports.resolve_wsl_interop", lambda: "/run/WSL/test_interop")
    monkeypatch.setattr("zotero_gpt_mirror.transports.resolve_windows_curl", lambda name: "/mnt/c/Windows/System32/curl.exe")
    calls = []
    envs = []
    cwds = []

    def fake_run(args, check, capture_output, text, timeout, env, cwd):
        calls.append(args)
        envs.append(env)
        cwds.append(cwd)

        class Result:
            returncode = 0
            stdout = "HTTP/1.1 200 OK\r\n\r\n[]"
            stderr = ""

        return Result()

    monkeypatch.setattr("zotero_gpt_mirror.transports.subprocess.run", fake_run)
    transport = WindowsInteropTransport("http://127.0.0.1:23119/api/", cmd_exe="/mnt/c/Windows/System32/cmd.exe")
    response = transport.get("users/0/items")
    assert response.status == 200
    assert response.body == "[]"
    assert calls[0][0] == "/mnt/c/Windows/System32/curl.exe"
    assert "--noproxy" in calls[0]
    assert envs[0]["WSL_INTEROP"] == "/run/WSL/test_interop"
    assert cwds[0] == "/mnt/c/Windows/System32"
