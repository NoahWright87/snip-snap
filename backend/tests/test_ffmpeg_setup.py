import sys
import threading
import time
import zipfile
from pathlib import Path

from app import ffmpeg_setup


def test_ensure_ffmpeg_ready_sets_ready_when_already_available(monkeypatch):
    monkeypatch.setattr(ffmpeg_setup.ffmpeg_locate, "is_available", lambda: True)
    ffmpeg_setup.ensure_ffmpeg_ready()
    assert ffmpeg_setup.get_status()["state"] == "ready"


def test_ensure_ffmpeg_ready_errors_on_non_windows_when_missing(monkeypatch):
    monkeypatch.setattr(ffmpeg_setup.ffmpeg_locate, "is_available", lambda: False)
    monkeypatch.setattr(ffmpeg_setup.sys, "platform", "linux")
    ffmpeg_setup.ensure_ffmpeg_ready()
    status = ffmpeg_setup.get_status()
    assert status["state"] == "error"
    assert "manually" in status["message"]


def test_ensure_ffmpeg_ready_kicks_off_background_download_on_windows(monkeypatch):
    monkeypatch.setattr(ffmpeg_setup.ffmpeg_locate, "is_available", lambda: False)
    monkeypatch.setattr(ffmpeg_setup.sys, "platform", "win32")

    ran = threading.Event()
    monkeypatch.setattr(ffmpeg_setup, "_download_and_install", ran.set)

    ffmpeg_setup.ensure_ffmpeg_ready()

    assert ffmpeg_setup.get_status()["state"] == "downloading"
    assert ran.wait(timeout=2)


def test_download_writes_file_and_reports_completion(tmp_path, monkeypatch):
    payload = b"hello ffmpeg payload" * 100

    class _FakeResponse:
        def __init__(self, data: bytes):
            self._chunks = [data[i : i + 32] for i in range(0, len(data), 32)]
            self.headers = {"Content-Length": str(len(data))}

        def read(self, n):
            return self._chunks.pop(0) if self._chunks else b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        ffmpeg_setup.urllib.request, "urlopen", lambda url, timeout=30: _FakeResponse(payload)
    )

    dest = tmp_path / "ffmpeg.zip"
    ffmpeg_setup._download("http://example.test/ffmpeg.zip", dest)

    assert dest.read_bytes() == payload
    assert ffmpeg_setup.get_status()["progress"] == 1.0


def test_extract_binaries_pulls_only_the_named_binaries(tmp_path):
    zip_path = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("ffmpeg-build-1234/bin/ffmpeg.exe", "fake ffmpeg contents")
        zf.writestr("ffmpeg-build-1234/bin/ffprobe.exe", "fake ffprobe contents")
        zf.writestr("ffmpeg-build-1234/bin/ffplay.exe", "not wanted")
        zf.writestr("ffmpeg-build-1234/doc/readme.txt", "not wanted either")

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    ffmpeg_setup._extract_binaries(zip_path, dest_dir)

    assert (dest_dir / "ffmpeg.exe").read_text() == "fake ffmpeg contents"
    assert (dest_dir / "ffprobe.exe").read_text() == "fake ffprobe contents"
    assert not (dest_dir / "ffplay.exe").exists()
    assert not (dest_dir / ".part").exists()


def test_extract_binaries_raises_if_something_is_missing(tmp_path):
    zip_path = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("ffmpeg-build-1234/bin/ffmpeg.exe", "fake ffmpeg contents")

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    try:
        ffmpeg_setup._extract_binaries(zip_path, dest_dir)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "missing" in str(exc)
