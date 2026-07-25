import json
import os
import urllib.request
from dataclasses import dataclass

from app import build_info

LATEST_RELEASE_API_URL = os.environ.get(
    "SNIPSNAP_RELEASES_LATEST_API_URL",
    "https://api.github.com/repos/NoahWright87/snip-snap/releases/latest",
)
DOWNLOADS_PAGE_URL = os.environ.get(
    "SNIPSNAP_RELEASES_PAGE_URL",
    "https://github.com/NoahWright87/snip-snap/releases/latest",
)
REQUEST_TIMEOUT_SECONDS = 2.5


@dataclass(frozen=True)
class LatestRelease:
    version: str
    html_url: str


def normalize_version(raw: str) -> str:
    value = raw.strip()
    return value[1:] if value.startswith(("v", "V")) else value


def get_current_version() -> str:
    return normalize_version(build_info.APP_VERSION)


def _parse_numeric_version(version: str) -> tuple[int, ...] | None:
    core = version.split("-", 1)[0]
    parts = core.split(".")
    numbers: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        numbers.append(int(part))
    return tuple(numbers)


def is_newer_version(current: str, latest: str) -> bool:
    current_normalized = normalize_version(current)
    latest_normalized = normalize_version(latest)
    current_parts = _parse_numeric_version(current_normalized)
    latest_parts = _parse_numeric_version(latest_normalized)
    if current_parts is not None and latest_parts is not None:
        max_len = max(len(current_parts), len(latest_parts))
        padded_current = current_parts + (0,) * (max_len - len(current_parts))
        padded_latest = latest_parts + (0,) * (max_len - len(latest_parts))
        return padded_latest > padded_current
    return latest_normalized != current_normalized


def fetch_latest_release() -> LatestRelease:
    req = urllib.request.Request(
        LATEST_RELEASE_API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "snip-snap"},
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        payload = json.load(resp)

    tag_name = payload.get("tag_name")
    if not isinstance(tag_name, str) or not tag_name.strip():
        raise ValueError("latest release response missing tag_name")

    html_url = payload.get("html_url")
    resolved_url = html_url if isinstance(html_url, str) and html_url.strip() else DOWNLOADS_PAGE_URL
    return LatestRelease(version=normalize_version(tag_name), html_url=resolved_url)

