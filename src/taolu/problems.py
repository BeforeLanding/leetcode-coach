"""题目元数据：只存题号、slug、标题、难度、难度分，不存题面。"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

URL_BASE = "https://leetcode.cn/problems/"
FIELDS = ("id", "slug", "title", "difficulty", "rating")


@dataclass(frozen=True)
class Problem:
    id: int
    slug: str
    title: str
    difficulty: str
    rating: float | None = None

    @property
    def url(self) -> str:
        return f"{URL_BASE}{self.slug}/"


def load_csv(path: Path) -> list[Problem]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"{path}: 表头必须是 {','.join(FIELDS)}，实际为 {reader.fieldnames}")
        out = []
        for lineno, row in enumerate(reader, start=2):
            try:
                out.append(
                    Problem(
                        id=int(row["id"]),
                        slug=row["slug"].strip(),
                        title=row["title"].strip(),
                        difficulty=row["difficulty"].strip(),
                        rating=float(row["rating"]) if row["rating"].strip() else None,
                    )
                )
            except (ValueError, AttributeError) as e:
                raise ValueError(f"{path}:{lineno}: {e}") from e
    return out


def upsert(conn: sqlite3.Connection, problems: list[Problem]) -> int:
    conn.executemany(
        """
        INSERT INTO problem (id, slug, title, difficulty, rating)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            slug = excluded.slug, title = excluded.title,
            difficulty = excluded.difficulty, rating = excluded.rating
        """,
        [(p.id, p.slug, p.title, p.difficulty, p.rating) for p in problems],
    )
    return len(problems)


def get(conn: sqlite3.Connection, problem_id: int) -> Problem | None:
    row = conn.execute(
        "SELECT id, slug, title, difficulty, rating FROM problem WHERE id = ?", (problem_id,)
    ).fetchone()
    return Problem(**dict(row)) if row else None
