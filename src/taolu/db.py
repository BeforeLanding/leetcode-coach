"""SQLite 存储。schema 版本记在 PRAGMA user_version。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from taolu import paths

SCHEMA_V1 = """
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

-- attempt 的 max_hint_level 即“当前提示层”；card_review 留给 M3
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


SCHEMA_V2 = [
    """
    CREATE TABLE attempt_step (
        attempt_id INTEGER NOT NULL REFERENCES attempt(id) ON DELETE CASCADE,
        level      INTEGER NOT NULL CHECK (level BETWEEN 0 AND 4),
        note       TEXT,              -- 进入下一层之前用户写的想法或代码
        skipped    INTEGER NOT NULL DEFAULT 0,
        at         TEXT NOT NULL,
        PRIMARY KEY (attempt_id, level)
    )
    """,
    # 同一时间最多一个进行中的 attempt：用常量表达式上的部分唯一索引在库层兜底
    "CREATE UNIQUE INDEX one_active_attempt ON attempt((1)) WHERE ended_at IS NULL",
]


def _migrate_to_v1(conn: sqlite3.Connection) -> None:
    for stmt in SCHEMA_V1.split(";"):
        if stmt.strip():
            conn.execute(stmt)


def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    for stmt in SCHEMA_V2:
        conn.execute(stmt)


# MIGRATIONS[i] 把 schema 从版本 i 升到 i+1；新增迁移只在末尾追加
MIGRATIONS = [_migrate_to_v1, _migrate_to_v2]
SCHEMA_VERSION = len(MIGRATIONS)


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
    for target in range(version + 1, SCHEMA_VERSION + 1):
        # 每一级一个事务：DDL 在 SQLite 里可回滚，失败时库停在上一个完整版本
        conn.execute("BEGIN")
        try:
            MIGRATIONS[target - 1](conn)
            conn.execute(f"PRAGMA user_version = {target}")
        except BaseException:
            conn.rollback()
            raise
        conn.commit()
