"""taolu 命令行。插件里的 slash command 都是调这里。

内容文件（cards/、data/problems.csv）是唯一事实来源：每条命令执行前都会把它们
同步进 SQLite（量很小，开销可忽略），所以手改卡片后不需要额外步骤。
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from taolu import __version__, cards, db, paths, problems


def _open() -> tuple[sqlite3.Connection, list[cards.Card]]:
    conn = db.connect()
    with conn:
        problems.upsert(conn, problems.load_csv(paths.problems_csv()))
        all_cards = cards.load_dir(paths.cards_dir())
        cards.sync(conn, all_cards)
    return conn, all_cards


def cmd_init(_: argparse.Namespace) -> int:
    conn, all_cards = _open()
    (n_problems,) = conn.execute("SELECT COUNT(*) FROM problem").fetchone()
    print(f"数据库：{paths.db_path()}")
    print(f"已同步 {n_problems} 道题、{len(all_cards)} 张套路卡")
    return 0


def cmd_card_list(_: argparse.Namespace) -> int:
    _, all_cards = _open()
    by_cat: dict[str, list[cards.Card]] = {}
    for c in all_cards:
        by_cat.setdefault(c.category, []).append(c)
    for cat, cs in by_cat.items():
        print(f"## {cat}")
        for c in cs:
            print(f"- {c.name}（{c.id}）· {len(c.problems)} 题")
    return 0


def cmd_card_show(args: argparse.Namespace) -> int:
    conn, all_cards = _open()
    card = cards.resolve(all_cards, " ".join(args.query))
    print(f"# {card.name}（{card.id}）")
    print(f"分类：{card.category}")
    if card.signals:
        print(f"适用信号：{'；'.join(card.signals)}")
    print()
    print(card.body, end="")
    print()
    print("## 练习题（按推荐顺序）")
    for pid in card.problems:
        p = problems.get(conn, pid)
        assert p is not None  # sync 已校验题号存在
        print(f"- {p.id}. {p.title}（{p.difficulty}）{p.url}")
    return 0


def cmd_problem_show(args: argparse.Namespace) -> int:
    conn, _ = _open()
    p = problems.get(conn, args.id)
    if p is None:
        raise LookupError(f"题库里没有 {args.id} 号题（M0 只收录了套路卡用到的题）")
    print(f"{p.id}. {p.title}（{p.difficulty}）")
    print(p.url)
    rows = conn.execute(
        "SELECT c.name, c.id FROM problem_card pc JOIN card c ON c.id = pc.card_id "
        "WHERE pc.problem_id = ? ORDER BY c.name",
        (p.id,),
    ).fetchall()
    if rows and args.reveal:
        print("套路卡：" + "、".join(f"{r['name']}({r['id']})" for r in rows))
    elif rows:
        print("（已关联套路卡；加 --reveal 查看，做题前建议别看）")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taolu", description="LeetCode 刷题教练")
    parser.add_argument("--version", action="version", version=f"taolu {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="初始化数据库并同步题目与套路卡").set_defaults(func=cmd_init)

    card = sub.add_parser("card", help="套路卡").add_subparsers(dest="card_cmd", required=True)
    card.add_parser("list", help="列出全部套路卡").set_defaults(func=cmd_card_list)
    show = card.add_parser("show", help="查看一张套路卡（id 或名称，支持唯一子串）")
    show.add_argument("query", nargs="+")
    show.set_defaults(func=cmd_card_show)

    prob = sub.add_parser("problem", help="题目").add_subparsers(dest="problem_cmd", required=True)
    pshow = prob.add_parser("show", help="查看题目元数据")
    pshow.add_argument("id", type=int)
    pshow.add_argument("--reveal", action="store_true", help="同时显示所属套路卡（会剧透）")
    pshow.set_defaults(func=cmd_problem_show)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认编码可能不是 UTF-8，统一输出编码，避免中文乱码/报错
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (LookupError, ValueError, RuntimeError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
