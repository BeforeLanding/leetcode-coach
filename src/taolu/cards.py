"""套路卡：cards/*.md，开头是一段受限格式的 frontmatter。

frontmatter 只支持两种行（刻意不引入 YAML 依赖）：
    key: 标量
    key: [a, b, c]     # 逗号分隔的行内列表
必填键：id、name、category、problems（题号列表，顺序即推荐顺序）。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED = ("id", "name", "category", "problems")


@dataclass
class Card:
    id: str
    name: str
    category: str
    problems: list[int]
    body: str
    path: Path
    signals: list[str] = field(default_factory=list)


def _parse_value(raw: str) -> str | list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [x.strip() for x in inner.split(",") if x.strip()] if inner else []
    return raw


def parse(path: Path) -> Card:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: 缺少 frontmatter（第一行必须是 ---）")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError(f"{path}: frontmatter 没有闭合的 ---") from None

    meta: dict[str, str | list[str]] = {}
    for lineno, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"{path}:{lineno}: 应为 'key: value'")
        meta[key.strip()] = _parse_value(value)

    missing = [k for k in REQUIRED if k not in meta]
    if missing:
        raise ValueError(f"{path}: frontmatter 缺少 {', '.join(missing)}")
    problems = meta["problems"]
    if not isinstance(problems, list):
        raise ValueError(f"{path}: problems 必须是 [题号, ...] 列表")
    try:
        problem_ids = [int(p) for p in problems]
    except ValueError as e:
        raise ValueError(f"{path}: problems 里有非整数题号：{e}") from e
    signals = meta.get("signals", [])

    return Card(
        id=str(meta["id"]),
        name=str(meta["name"]),
        category=str(meta["category"]),
        problems=problem_ids,
        signals=signals if isinstance(signals, list) else [signals],
        body="\n".join(lines[end + 1 :]).strip() + "\n",
        path=path,
    )


def load_dir(directory: Path) -> list[Card]:
    cards = [parse(p) for p in sorted(directory.glob("*.md"))]
    seen: dict[str, Path] = {}
    for c in cards:
        for key in (c.id, c.name):
            if key in seen:
                raise ValueError(f"卡片 id/名称重复：{key!r} 同时出现在 {seen[key]} 和 {c.path}")
            seen[key] = c.path
    return cards


def sync(conn: sqlite3.Connection, cards: list[Card]) -> int:
    """以文件为准全量同步：文件里删掉的卡也从库里删掉。"""
    known = {row[0] for row in conn.execute("SELECT id FROM problem")}
    for c in cards:
        unknown = [p for p in c.problems if p not in known]
        if unknown:
            raise ValueError(f"{c.path}: 题号 {unknown} 不在 data/problems.csv 里")

    ids = [c.id for c in cards]
    conn.execute(
        f"DELETE FROM card WHERE id NOT IN ({','.join('?' * len(ids))})", ids
    )
    for c in cards:
        conn.execute(
            """
            INSERT INTO card (id, name, category, file_path) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name, category = excluded.category, file_path = excluded.file_path
            """,
            (c.id, c.name, c.category, str(c.path)),
        )
        conn.execute("DELETE FROM problem_card WHERE card_id = ?", (c.id,))
        conn.executemany(
            "INSERT INTO problem_card (problem_id, card_id, ord) VALUES (?, ?, ?)",
            [(pid, c.id, i) for i, pid in enumerate(c.problems)],
        )
    return len(cards)


def resolve(cards: list[Card], query: str) -> Card:
    """按 id 或名称精确匹配；否则按子串匹配，要求唯一。"""
    q = query.strip()
    for c in cards:
        if q in (c.id, c.name):
            return c
    hits = [c for c in cards if q and (q in c.id or q in c.name)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise LookupError(f"找不到套路卡：{q!r}（用 `taolu card list` 查看全部）")
    names = "、".join(f"{c.name}({c.id})" for c in hits)
    raise LookupError(f"{q!r} 匹配到多张卡：{names}，请写得更具体")
