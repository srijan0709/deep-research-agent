"""SQLite database access.

The persistence layer is intentionally thin: raw sqlite3 with a simple
connection factory. Repositories (repositories.py) are the abstraction the
rest of the application depends on, so swapping SQLite for PostgreSQL later
only requires changing this module + repositories.py.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

_DB_PATH = settings.database_url.replace("sqlite:///", "")
_local = threading.local()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_jobs (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    depth TEXT,
    status TEXT NOT NULL,
    title TEXT,
    objective TEXT,
    created_at TEXT,
    updated_at TEXT,
    completed_at TEXT,
    error TEXT,
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    report TEXT,
    model TEXT,
    prompt_version TEXT
);

CREATE TABLE IF NOT EXISTS research_tasks (
    id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    question TEXT,
    priority TEXT,
    search_queries TEXT,
    status TEXT,
    attempt INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    result TEXT,
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    url TEXT,
    title TEXT,
    publisher TEXT,
    published_at TEXT,
    retrieved_at TEXT,
    source_type TEXT,
    content_hash TEXT,
    relevance_score REAL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    research_id TEXT NOT NULL,
    task_id TEXT,
    text TEXT,
    url TEXT,
    title TEXT,
    publisher TEXT,
    published_at TEXT,
    retrieved_at TEXT,
    relevance_score REAL
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    task_id TEXT,
    text TEXT,
    confidence REAL,
    verification_status TEXT,
    reason TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    relationship TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    research_id TEXT PRIMARY KEY,
    data TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_id TEXT,
    data TEXT,
    created_at TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        conn.commit()
        _local.conn = conn
    return _local.conn


@contextmanager
def transaction():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
