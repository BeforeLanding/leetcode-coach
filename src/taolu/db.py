"""SQLite 存储。schema 版本记在 PRAGMA user_version。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from taolu import paths

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS problem (
    id          INTEGER PRIMARY KEY,          -- 力扣题号
    slug        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    difficulty  TEXT NOT NULL CHECK (difficulty IN ('Easy', 'Medium', 'Hard')),
    rating      REAL                           -- 周赛难度分，可为空
);

CREATE TABLE IF NOT EXISTS card (
    id          TEXT PRIMARY KEY,             -- 如 sliding-window
    name        TEXT NOT NULL UNIQUE,         -- 如 不定长滑动窗口
    category    TEXT NOT NULL,
    file_path   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS problem_card (
    problem_id  INTEGER NOT NULL REFERENCES problem(id),
    card_id     TEXT NOT NULL REFERENCES card(id) ON DELETE CASCADE,
    ord         INTEGER NOT NULL,             -- 在卡片里的推荐顺序
    PRIMARY KEY (problem_id, card_id)
);

-- 以下两张表 M1/M3 才会写入，先建好避免后续迁移
CREATE TABLE IF NOT EXISTS attempt (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id      INTEGER NOT NULL REFERENCES problem(id),
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    max_hint_level  INTEGER NOT NULL DEFAULT 0 CHECK (max_hint_level BETWEEN 0 AND 4),
    accepted        INTEGER,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS card_review (
    card_id      TEXT PRIMARY KEY REFERENCES card(id) ON DELETE CASCADE,
    due          TEXT NOT NULL,
    stability    REAL NOT NULL,
    difficulty   REAL NOT NULL,
    reps         INTEGER NOT NULL DEFAULT 0,
    lapses       INTEGER NOT NULL DEFAULT 0,
    last_review  TEXT
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or paths.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    (version,) = conn.execute("PRAGMA user_version").fetchone()
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"数据库 schema 版本 {version} 比程序支持的 {SCHEMA_VERSION} 新，请升级 taolu"
        )
    if version < SCHEMA_VERSION:
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
