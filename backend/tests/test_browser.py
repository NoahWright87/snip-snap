from pathlib import Path

from app import browser


def test_find_chromium_browser_returns_none_or_an_existing_file():
    result = browser.find_chromium_browser()
    assert result is None or Path(result).is_file()


def test_open_app_window_falls_back_to_webbrowser_when_none_found(monkeypatch):
    monkeypatch.setattr(browser, "find_chromium_browser", lambda: None)
    calls = []
    monkeypatch.setattr(browser.webbrowser, "open", lambda url: calls.append(url))

    browser.open_app_window("http://example.test")

    assert calls == ["http://example.test"]


def test_open_app_window_launches_browser_in_app_mode(monkeypatch):
    monkeypatch.setattr(browser, "find_chromium_browser", lambda: "/usr/bin/fake-chrome")
    calls = []
    monkeypatch.setattr(browser.subprocess, "Popen", lambda args: calls.append(args))

    browser.open_app_window("http://example.test")

    assert calls == [["/usr/bin/fake-chrome", "--app=http://example.test"]]
