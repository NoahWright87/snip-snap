import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    duration REAL,
    source_type TEXT NOT NULL DEFAULT 'unpaired'
        CHECK (source_type IN ('raw', 'edited', 'unpaired')),
    paired_video_id INTEGER REFERENCES videos(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('keep', 'cut')),
    provenance TEXT NOT NULL DEFAULT 'manual'
        CHECK (provenance IN ('manual', 'diff_inferred', 'suggested_confirmed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A segment can carry multiple tags (e.g. both "boring" and "off-topic").
CREATE TABLE IF NOT EXISTS segment_tags (
    segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (segment_id, tag)
);

CREATE TABLE IF NOT EXISTS embeddings_cache (
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    embedding_path TEXT NOT NULL,
    PRIMARY KEY (video_id, segment_id)
);

CREATE TABLE IF NOT EXISTS classifier_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT NOT NULL,
    trained_at TEXT NOT NULL DEFAULT (datetime('now')),
    training_segment_count INTEGER NOT NULL,
    model_path TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_segments_video_id ON segments(video_id);
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
