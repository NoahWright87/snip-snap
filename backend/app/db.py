import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from app import config

# Video/segment/tag data lives in a .snipsnap.json sidecar inside each
# ingested folder (see app/store.py) - this database only remembers which
# folders have been registered, so the library view knows where to look.
SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db(db_path: Optional[Path] = None) -> None:
    db_path = db_path or config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_db(db_path: Optional[Path] = None):
    db_path = db_path or config.DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
