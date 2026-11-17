"""taolu 命令行。插件里的 slash command 都是调这里。

内容文件（cards/、data/problems.csv）是唯一事实来源：每条命令执行前都会把它们
同步进 SQLite（量很小，开销可忽略），所以手改卡片后不需要额外步骤。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from taolu import __version__, cards, db, explain, paths, problems, sessions, solutions


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


def _read_input(file: str | None) -> str:
    if file:
        try:
            return Path(file).read_text(encoding="utf-8-sig")
        except OSError as e:
            raise ValueError(f"读不了 {file}：{e}") from e
    return sys.stdin.read()


def _known_problem(conn: sqlite3.Connection, problem_id: int) -> problems.Problem:
    p = problems.get(conn, problem_id)
    if p is None:
        raise LookupError(
            f"题库里没有 {problem_id} 号题。可用 `taolu problem add {problem_id} <slug> <标题> <Easy|Medium|Hard>` 添加"
        )
    return p


def cmd_card_link(args: argparse.Namespace) -> int:
    conn, all_cards = _open()
    _known_problem(conn, args.id)
    card = next((c for c in all_cards if c.id == args.card), None)
    if card is None:
        raise LookupError(f"找不到卡片 id {args.card!r}（用 `taolu card list` 查看）")
    cards.link_problem(card, args.id)
    print(f"已把 {args.id} 号题关联到 {card.name}（{card.id}）：{card.path}")
    return 0


def cmd_solution_save(args: argparse.Namespace) -> int:
    conn, _ = _open()
    _known_problem(conn, args.id)
    n = solutions.save(args.id, _read_input(args.file), source=args.source, lang=args.lang)
    print(f"已保存 {args.id} 号题第 {n} 份题解（仅本地：{paths.solutions_dir() / str(args.id)}）")
    return 0


def cmd_solution_list(args: argparse.Namespace) -> int:
    conn, _ = _open()
    ids = [args.id] if args.id is not None else solutions.problems_with_solutions()
    if not ids:
        print("还没有缓存任何题解")
        return 0
    for pid in ids:
        items = solutions.list_for(pid)
        if not items:
            print(f"{pid} 号题还没有缓存题解")
        for s in items:
            print(f"{pid} #{s.n} · {s.lang} · {s.source or '（无来源）'} · {s.saved_at}")
    return 0


def cmd_solution_show(args: argparse.Namespace) -> int:
    conn, _ = _open()
    _known_problem(conn, args.id)
    explain.require_spoiler_ok(conn, args.id)
    print(solutions.get(args.id, args.n).text, end="")
    return 0


def cmd_explain_context(args: argparse.Namespace) -> int:
    conn, all_cards = _open()
    ctx = explain.context(conn, all_cards, args.id)
    if args.json:
        print(json.dumps(ctx, ensure_ascii=False, indent=2))
        return 0
    p = ctx["problem"]
    print(f"{p['id']}. {p['title']}（{p['difficulty']}）{p['url']}")
    print(f"题解 {len(ctx['solutions'])} 份；关联卡：" + ("、".join(c["name"] for c in ctx["cards"]) or "无"))
    print(f"拆解笔记：{'已有' if ctx['existing_note'] else '无'}（完整内容请用 --json）")
    return 0


def cmd_explain_save(args: argparse.Namespace) -> int:
    conn, _ = _open()
    path = explain.save_note(conn, args.id, _read_input(args.file))
    print(f"已保存拆解笔记（仅本地）：{path}")
    return 0


def cmd_explain_show(args: argparse.Namespace) -> int:
    conn, _ = _open()
    print(explain.show_note(conn, args.id), end="")
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

    clink = card.add_parser("link", help="把一道题追加到套路卡的 problems 列表（只改那一行）")
    clink.add_argument("id", type=int, help="题号")
    clink.add_argument("card", help="卡片 id")
    clink.set_defaults(func=cmd_card_link)

    sol = sub.add_parser("solution", help="本地题解缓存（只存 ~/.taolu，不进仓库）").add_subparsers(
        dest="solution_cmd", required=True
    )
    ssave = sol.add_parser("save", help="保存一份题解正文（--file 或 stdin）")
    ssave.add_argument("id", type=int)
    ssave.add_argument("--source", default="", help="来源链接，仅作记录，不会被抓取")
    ssave.add_argument("--lang", default="other", choices=solutions.LANGS)
    ssave.add_argument("--file", help="从文件读取；不给则读 stdin")
    ssave.set_defaults(func=cmd_solution_save)
    slist = sol.add_parser("list", help="列出已缓存的题解（不打印正文）")
    slist.add_argument("id", type=int, nargs="?")
    slist.set_defaults(func=cmd_solution_list)
    sshow = sol.add_parser("show", help="打印题解正文，默认最新一份（会剧透）")
    sshow.add_argument("id", type=int)
    sshow.add_argument("--n", type=int)
    sshow.set_defaults(func=cmd_solution_show)

    exp = sub.add_parser("explain", help="解法拆解（会剧透）").add_subparsers(
        dest="explain_cmd", required=True
    )
    ectx = exp.add_parser("context", help="讲解所需的全部材料")
    ectx.add_argument("id", type=int)
    ectx.add_argument("--json", action="store_true")
    ectx.set_defaults(func=cmd_explain_context)
    esave = exp.add_parser("save", help="保存拆解笔记（--file 或 stdin），覆盖前留 .bak")
    esave.add_argument("id", type=int)
    esave.add_argument("--file")
    esave.set_defaults(func=cmd_explain_save)
    eshow = exp.add_parser("show", help="打印拆解笔记")
    eshow.add_argument("id", type=int)
    eshow.set_defaults(func=cmd_explain_show)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认编码可能不是 UTF-8，统一输出编码，避免中文乱码/报错；
    # stdin 用 utf-8-sig，兼容 PowerShell 管道可能带的 BOM
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8-sig")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (LookupError, ValueError, RuntimeError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
