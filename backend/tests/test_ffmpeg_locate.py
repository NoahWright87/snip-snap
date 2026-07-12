import sys

from app import ffmpeg_locate


def test_uses_path_lookup_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(ffmpeg_locate.shutil, "which", lambda name: f"/usr/bin/{name}")

    assert ffmpeg_locate.ffmpeg_path() == "/usr/bin/ffmpeg"
    assert ffmpeg_locate.ffprobe_path() == "/usr/bin/ffprobe"


def test_returns_none_when_not_found_anywhere(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(ffmpeg_locate.shutil, "which", lambda name: None)

    assert ffmpeg_locate.ffmpeg_path() is None
    assert ffmpeg_locate.is_available() is False


def test_prefers_downloaded_cache_over_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_locate, "config", ffmpeg_locate.config)
    monkeypatch.setattr(ffmpeg_locate.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ffmpeg_locate.sys, "platform", "linux")

    cache = tmp_path / "ffmpeg_bin"
    cache.mkdir()
    (cache / "ffmpeg").write_text("stub")

    # Even if ffmpeg also exists on PATH, the cached copy wins.
    monkeypatch.setattr(ffmpeg_locate.shutil, "which", lambda name: f"/usr/bin/{name}")

    assert ffmpeg_locate.ffmpeg_path() == str(cache / "ffmpeg")
    # ffprobe isn't cached, so it falls back to PATH.
    assert ffmpeg_locate.ffprobe_path() == "/usr/bin/ffprobe"
