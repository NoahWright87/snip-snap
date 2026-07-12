import asyncio
import os
import threading
import time

from app.config import HEARTBEAT_TIMEOUT_SECONDS, INACTIVITY_CHECK_INTERVAL_SECONDS

_last_heartbeat = time.monotonic()


def record_heartbeat() -> None:
    global _last_heartbeat
    _last_heartbeat = time.monotonic()


def seconds_since_heartbeat() -> float:
    return time.monotonic() - _last_heartbeat


def request_shutdown(delay_seconds: float = 0.2) -> None:
    """Exit the process shortly after returning a response to the caller."""

    def _exit():
        time.sleep(delay_seconds)
        os._exit(0)

    threading.Thread(target=_exit, daemon=True).start()


async def watch_inactivity() -> None:
    """Background task: shut down if no heartbeat has arrived in time.

    Covers the case where the frontend tab crashes or is killed without
    getting a chance to send its pagehide beacon to /api/shutdown.
    """
    while True:
        await asyncio.sleep(INACTIVITY_CHECK_INTERVAL_SECONDS)
        if seconds_since_heartbeat() > HEARTBEAT_TIMEOUT_SECONDS:
            os._exit(0)
