"""explain：把讲解需要的东西一次交给模型，并存取生成的拆解笔记（只在本地）。

门禁：explain 会剧透全部内容，所以这道题有进行中的 attempt 且层级 < 4 时一律拒绝。
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from taolu import cards, paths, problems, sessions, solutions

NEXT_PER_CARD = 3


def require_spoiler_ok(conn: sqlite3.Connection, problem_id: int) -> None:
    att = sessions.active(conn)
    if att is not None and att["problem_id"] == problem_id and att["max_hint_level"] < sessions.MAX_LEVEL:
        raise RuntimeError(
            f"你正在做 {problem_id} 号题（L{att['max_hint_level']}），题解和拆解会剧透全部内容。"
            "先做完（`session end`）/放弃（`session abandon`），或推进到 L4"
        )


def _problem(conn: sqlite3.Connection, problem_id: int) -> problems.Problem:
    p = problems.get(conn, problem_id)
    if p is None:
        raise LookupError(
            f"题库里没有 {problem_id} 号题。可用 `taolu problem add {problem_id} <slug> <标题> <Easy|Medium|Hard>` 添加"
        )
    return p


def note_path(problem_id: int) -> Path:
    return paths.notes_dir() / f"{problem_id}.md"


def context(conn: sqlite3.Connection, all_cards: list[cards.Card], problem_id: int) -> dict:
    p = _problem(conn, problem_id)
    require_spoiler_ok(conn, problem_id)
    by_id = {c.id: c for c in all_cards}
    linked_ids = [
        r["card_id"]
        for r in conn.execute(
            "SELECT card_id FROM problem_card WHERE problem_id = ? ORDER BY ord, card_id", (p.id,)
        )
    ]
    linked = [by_id[i] for i in linked_ids if i in by_id]
    # 正在做、且没到 L4 的另一道题不能出现在推荐里：它出现在哪张卡下面，就等于说出了它的套路
    att = sessions.active(conn)
    hidden = (
        att["problem_id"]
        if att is not None and att["max_hint_level"] < sessions.MAX_LEVEL
        else -1
    )
    next_candidates = []
    for c in linked:
        rows = conn.execute(
            """
            SELECT p.id, p.title, p.difficulty
            FROM problem_card pc JOIN problem p ON p.id = pc.problem_id
            WHERE pc.card_id = ? AND p.id != ? AND p.id != ?
              AND NOT EXISTS (SELECT 1 FROM attempt a WHERE a.problem_id = p.id AND a.accepted = 1)
            ORDER BY pc.ord LIMIT ?
            """,
            (c.id, p.id, hidden, NEXT_PER_CARD),
        ).fetchall()
        next_candidates.append(
            {
                "card_id": c.id,
                "problems": [
                    {"id": r["id"], "title": r["title"], "difficulty": r["difficulty"]} for r in rows
                ],
            }
        )
    np = note_path(p.id)
    return {
        "problem": {"id": p.id, "title": p.title, "difficulty": p.difficulty, "url": p.url},
        "solutions": [
            {"n": s.n, "lang": s.lang, "source": s.source, "text": s.text}
            for s in solutions.list_for(p.id)
        ],
        "cards": [
            {
                "id": c.id,
                "name": c.name,
                "signals": c.signals,
                "template": cards.extract_template(c.body),
            }
            for c in linked
        ],
        "next_candidates": next_candidates,
        "existing_note": np.read_text(encoding="utf-8") if np.exists() else None,
    }


def save_note(conn: sqlite3.Connection, problem_id: int, text: str) -> Path:
    _problem(conn, problem_id)
    if not text.strip():
        raise ValueError("笔记内容为空：请通过 --file 或 stdin 提供")
    path = note_path(problem_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copyfile(path, path.with_suffix(".md.bak"))
    path.write_text(text.replace("\r\n", "\n").rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    return path


def show_note(conn: sqlite3.Connection, problem_id: int) -> str:
    _problem(conn, problem_id)
    require_spoiler_ok(conn, problem_id)
    path = note_path(problem_id)
    if not path.exists():
        raise LookupError(f"{problem_id} 号题还没有拆解笔记，先用 `/taolu:explain {problem_id}` 生成")
    return path.read_text(encoding="utf-8")
