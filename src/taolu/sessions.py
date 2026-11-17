"""提示梯状态机：一次做题 = 一个 attempt，level 存在 attempt.max_hint_level。

门禁（reveal）只在这里算：level<2 时不含任何卡片信息，level<3 时不含模板。
skill 只能讲 reveal 里给出的内容，所以这是“不剧透”的唯一防线，必须有测试。
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from taolu import cards, problems

MAX_LEVEL = 4
CARD_LEVEL = 2  # 从这一层起可以透露套路名
TEMPLATE_LEVEL = 3  # 从这一层起可以给模板骨架


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def active(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM attempt WHERE ended_at IS NULL").fetchone()


def _require_active(conn: sqlite3.Connection) -> sqlite3.Row:
    row = active(conn)
    if row is None:
        raise LookupError("当前没有进行中的练习，先用 `taolu session start <题号>` 开始")
    return row


def start(conn: sqlite3.Connection, problem_id: int) -> problems.Problem:
    p = problems.get(conn, problem_id)
    if p is None:
        raise LookupError(
            f"题库里没有 {problem_id} 号题。"
            f"可用 `taolu problem add {problem_id} <slug> <标题> <Easy|Medium|Hard>` 添加"
        )
    cur = active(conn)
    if cur is not None:
        raise RuntimeError(
            f"已有进行中的练习（{cur['problem_id']} 号题，L{cur['max_hint_level']}）。"
            "先用 `taolu session end --ac|--no-ac` 结束，或 `taolu session abandon` 放弃"
        )
    with conn:
        conn.execute(
            "INSERT INTO attempt (problem_id, started_at, max_hint_level) VALUES (?, ?, 0)",
            (problem_id, _now()),
        )
    return p


def state(conn: sqlite3.Connection, all_cards: list[cards.Card]) -> dict:
    att = _require_active(conn)
    level = att["max_hint_level"]
    p = problems.get(conn, att["problem_id"])
    assert p is not None
    notes = [
        {"level": r["level"], "note": r["note"], "skipped": bool(r["skipped"])}
        for r in conn.execute(
            "SELECT level, note, skipped FROM attempt_step WHERE attempt_id = ? ORDER BY level",
            (att["id"],),
        )
    ]
    reveal: dict = {"cards": None, "template": None}
    if level >= CARD_LEVEL:
        by_id = {c.id: c for c in all_cards}
        rows = conn.execute(
            "SELECT card_id FROM problem_card WHERE problem_id = ? ORDER BY ord, card_id",
            (p.id,),
        ).fetchall()
        linked = [by_id[r["card_id"]] for r in rows if r["card_id"] in by_id]
        reveal["cards"] = [{"id": c.id, "name": c.name, "signals": c.signals} for c in linked]
        if level >= TEMPLATE_LEVEL:
            # 多张卡时取排在最前的那张的模板
            reveal["template"] = cards.extract_template(linked[0].body) if linked else None
    return {
        "attempt_id": att["id"],
        "problem": {"id": p.id, "title": p.title, "difficulty": p.difficulty, "url": p.url},
        "level": level,
        "max_level": MAX_LEVEL,
        "notes": notes,
        "reveal": reveal,
    }


def advance(conn: sqlite3.Connection, note: str | None, skip: bool) -> int:
    if skip == (note is not None):
        raise ValueError("--note 和 --skip 必须二选一")
    if note is not None and not note.strip():
        raise ValueError("--note 不能为空：先让用户写一句自己的想法（想跳过请用 --skip）")
    att = _require_active(conn)
    level = att["max_hint_level"]
    if level >= MAX_LEVEL:
        raise RuntimeError(f"已经在最高层 L{MAX_LEVEL}，不能再推进；用 end 或 abandon 结束")
    with conn:
        conn.execute(
            "INSERT INTO attempt_step (attempt_id, level, note, skipped, at) VALUES (?, ?, ?, ?, ?)",
            (att["id"], level, None if skip else note.strip(), int(skip), _now()),
        )
        conn.execute(
            "UPDATE attempt SET max_hint_level = ? WHERE id = ?", (level + 1, att["id"])
        )
    return level + 1


def _fmt_duration(seconds: int) -> str:
    m, s = divmod(max(seconds, 0), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h} 小时 {m} 分"
    return f"{m} 分 {s} 秒" if m else f"{s} 秒"


def finish(conn: sqlite3.Connection, accepted: bool | None) -> str:
    """accepted=None 表示放弃。返回中文小结。"""
    att = _require_active(conn)
    ended = _now()
    with conn:
        conn.execute(
            "UPDATE attempt SET ended_at = ?, accepted = ? WHERE id = ?",
            (ended, None if accepted is None else int(accepted), att["id"]),
        )
    p = problems.get(conn, att["problem_id"])
    assert p is not None
    (skipped,) = conn.execute(
        "SELECT COUNT(*) FROM attempt_step WHERE attempt_id = ? AND skipped = 1", (att["id"],)
    ).fetchone()
    seconds = int(
        (datetime.fromisoformat(ended) - datetime.fromisoformat(att["started_at"])).total_seconds()
    )
    result = "放弃" if accepted is None else ("AC" if accepted else "未 AC")
    level = att["max_hint_level"]
    return "\n".join(
        [
            f"小结：{p.id}. {p.title}（{p.difficulty}）",
            f"结果：{result}",
            f"用了 {level} 层提示（最高到 L{level}），其中跳过 {skipped} 层",
            f"耗时：{_fmt_duration(seconds)}",
        ]
    )
