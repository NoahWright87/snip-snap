import sys

from app import ffmpeg_locate


def test_uses_path_lookup_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert ffmpeg_locate.ffmpeg_path() == "ffmpeg"
    assert ffmpeg_locate.ffprobe_path() == "ffprobe"


def test_prefers_bundled_binary_when_frozen(tmp_path, monkeypatch):
    bundled = tmp_path / "ffmpeg_bin"
    bundled.mkdir()
    (bundled / "ffmpeg").write_text("stub")
    (bundled / "ffprobe").write_text("stub")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(ffmpeg_locate.sys, "platform", "linux")

    assert ffmpeg_locate.ffmpeg_path() == str(bundled / "ffmpeg")
    assert ffmpeg_locate.ffprobe_path() == str(bundled / "ffprobe")


def test_falls_back_to_path_when_frozen_but_bundle_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert ffmpeg_locate.ffmpeg_path() == "ffmpeg"
