"""taolu 命令行。插件里的 slash command 都是调这里。

内容文件（cards/、data/problems.csv）是唯一事实来源：每条命令执行前都会把它们
同步进 SQLite（量很小，开销可忽略），所以手改卡片后不需要额外步骤。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from taolu import __version__, cards, db, paths, problems, sessions


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


def cmd_problem_add(args: argparse.Namespace) -> int:
    problems.append_csv(
        paths.problems_csv(),
        problems.Problem(id=args.id, slug=args.slug, title=args.title, difficulty=args.difficulty),
    )
    print(f"已添加 {args.id}. {args.title}（{args.difficulty}）到 {paths.problems_csv()}")
    return 0


def cmd_session_start(args: argparse.Namespace) -> int:
    conn, _ = _open()
    p = sessions.start(conn, args.id)
    print(f"已开始：{p.id}. {p.title}（{p.difficulty}），当前 L0")
    return 0


def cmd_session_state(args: argparse.Namespace) -> int:
    conn, all_cards = _open()
    st = sessions.state(conn, all_cards)
    if args.json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0
    p = st["problem"]
    print(f"{p['id']}. {p['title']}（{p['difficulty']}）{p['url']}")
    print(f"当前层级：L{st['level']}（最高 L{st['max_level']}）")
    for n in st["notes"]:
        print(f"- L{n['level']}：{'（跳过）' if n['skipped'] else n['note']}")
    reveal = st["reveal"]
    if reveal["cards"] is not None:
        names = "、".join(f"{c['name']}（{c['id']}）" for c in reveal["cards"]) or "（无关联套路卡）"
        print(f"套路卡：{names}")
    if reveal["template"] is not None:
        print("模板：")
        print(reveal["template"], end="")
    return 0


def cmd_session_advance(args: argparse.Namespace) -> int:
    conn, _ = _open()
    level = sessions.advance(conn, args.note, args.skip)
    print(f"已进入 L{level}")
    return 0


def cmd_session_end(args: argparse.Namespace) -> int:
    conn, _ = _open()
    print(sessions.finish(conn, args.ac))
    return 0


def cmd_session_abandon(_: argparse.Namespace) -> int:
    conn, _cards = _open()
    print(sessions.finish(conn, None))
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

    padd = prob.add_parser("add", help="往 data/problems.csv 追加一道题的元数据")
    padd.add_argument("id", type=int)
    padd.add_argument("slug")
    padd.add_argument("title")
    padd.add_argument("difficulty", choices=problems.DIFFICULTIES)
    padd.set_defaults(func=cmd_problem_add)

    sess = sub.add_parser("session", help="做题会话（提示梯）").add_subparsers(
        dest="session_cmd", required=True
    )
    sstart = sess.add_parser("start", help="开始做一道题，level=0")
    sstart.add_argument("id", type=int)
    sstart.set_defaults(func=cmd_session_start)
    sstate = sess.add_parser("state", help="当前会话状态（只含当前层允许透露的信息）")
    sstate.add_argument("--json", action="store_true")
    sstate.set_defaults(func=cmd_session_state)
    sadv = sess.add_parser("advance", help="记录当前层的想法或跳过，然后进入下一层")
    grp = sadv.add_mutually_exclusive_group(required=True)
    grp.add_argument("--note", help="用户写的想法或代码")
    grp.add_argument("--skip", action="store_true", help="用户坚持跳过，记为看了提示")
    sadv.set_defaults(func=cmd_session_advance)
    send = sess.add_parser("end", help="结束会话并打印小结")
    res = send.add_mutually_exclusive_group(required=True)
    res.add_argument("--ac", dest="ac", action="store_true", default=None)
    res.add_argument("--no-ac", dest="ac", action="store_false", default=None)
    send.set_defaults(func=cmd_session_end)
    sess.add_parser("abandon", help="放弃：结束但不计 AC").set_defaults(func=cmd_session_abandon)
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
