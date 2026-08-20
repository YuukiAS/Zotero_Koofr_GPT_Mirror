from pathlib import Path

from zotero_gpt_mirror.paths import file_url_to_windows_path, file_url_to_wsl_path


def test_file_url_to_windows_path_decodes_drive_path() -> None:
    result = file_url_to_windows_path("file:///C:/Users/Alice/Zotero/storage/ABCD/Paper%20Name.pdf")
    assert result == "C:\\Users\\Alice\\Zotero\\storage\\ABCD\\Paper Name.pdf"


def test_file_url_to_wsl_path_uses_wslpath(monkeypatch) -> None:
    calls = []

    def fake_run(args, check, capture_output, text):
        calls.append(args)

        class Result:
            returncode = 0
            stdout = "/mnt/c/Users/Alice/Zotero/storage/ABCD/Paper Name.pdf\n"
            stderr = ""

        return Result()

    monkeypatch.setattr("zotero_gpt_mirror.paths.subprocess.run", fake_run)
    result = file_url_to_wsl_path("file:///C:/Users/Alice/Zotero/storage/ABCD/Paper%20Name.pdf")
    assert result == Path("/mnt/c/Users/Alice/Zotero/storage/ABCD/Paper Name.pdf")
    assert calls == [["wslpath", "-u", "C:\\Users\\Alice\\Zotero\\storage\\ABCD\\Paper Name.pdf"]]
