import sqlite3

import pytest

from taolu import cards, cli, db, paths, problems

CARD = """---
id: {id}
name: {name}
category: 测试
problems: [{problems}]
---
正文
"""


def write_card(root, id="a", name="甲", problems="1"):
    (root / "cards" / f"{id}.md").write_text(CARD.format(id=id, name=name, problems=problems), encoding="utf-8")


# ---- 仓库自带内容本身要合法：这是 M0 的验收 ----

def test_repo_content_is_consistent():
    all_cards = cards.load_dir(paths.cards_dir())
    assert len(all_cards) >= 5
    known = {p.id for p in problems.load_csv(paths.problems_csv())}
    for c in all_cards:
        assert c.problems, f"{c.id} 没有练习题"
        assert set(c.problems) <= known, f"{c.id} 引用了未收录的题"
        assert "```python" in c.body, f"{c.id} 缺少 Python 模板"


def test_card_show_by_chinese_name(capsys):
    assert cli.main(["card", "show", "滑动窗口"]) == 0
    out = capsys.readouterr().out
    assert "不定长滑动窗口（sliding-window）" in out
    assert "https://leetcode.cn/problems/longest-substring-without-repeating-characters/" in out


def test_init_reports_counts(capsys, isolated_home):
    assert cli.main(["init"]) == 0
    assert "已同步 25 道题、5 张套路卡" in capsys.readouterr().out
    assert (isolated_home / "taolu.db").exists()


def test_problem_show_hides_card_unless_revealed(capsys):
    cli.main(["problem", "show", "739"])
    out = capsys.readouterr().out
    assert "每日温度" in out and "单调栈" not in out
    cli.main(["problem", "show", "739", "--reveal"])
    assert "单调栈" in capsys.readouterr().out


# ---- 解析与同步 ----

def test_resolve_ambiguous_and_missing(content):
    write_card(content, "sw-long", "滑动窗口求最长")
    write_card(content, "sw-short", "滑动窗口求最短")
    all_cards = cards.load_dir(content / "cards")
    assert cards.resolve(all_cards, "sw-short").name == "滑动窗口求最短"
    with pytest.raises(LookupError, match="多张卡"):
        cards.resolve(all_cards, "滑动窗口")
    with pytest.raises(LookupError, match="找不到"):
        cards.resolve(all_cards, "动态规划")


def test_unknown_problem_id_is_rejected(content, capsys):
    write_card(content, problems="1, 9999")
    assert cli.main(["card", "list"]) == 1
    assert "9999" in capsys.readouterr().err


def test_duplicate_card_name_is_rejected(content):
    write_card(content, "a", "同名")
    write_card(content, "b", "同名")
    with pytest.raises(ValueError, match="重复"):
        cards.load_dir(content / "cards")


def test_missing_frontmatter_key(content):
    (content / "cards" / "bad.md").write_text("---\nid: x\nname: y\n---\n", encoding="utf-8")
    with pytest.raises(ValueError, match="缺少 category, problems"):
        cards.load_dir(content / "cards")


def test_deleted_card_file_is_removed_from_db(content):
    write_card(content, "a", "甲")
    write_card(content, "b", "乙", problems="1, 3")
    cli.main(["init"])
    (content / "cards" / "b.md").unlink()
    cli.main(["init"])
    conn = db.connect()
    assert [r[0] for r in conn.execute("SELECT id FROM card")] == ["a"]
    assert conn.execute("SELECT COUNT(*) FROM problem_card WHERE card_id = 'b'").fetchone()[0] == 0


def test_bad_csv_header(content):
    (content / "data" / "problems.csv").write_text("id,title\n1,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="表头"):
        problems.load_csv(paths.problems_csv())


def test_newer_schema_refused(isolated_home):
    isolated_home.mkdir(parents=True)
    raw = sqlite3.connect(isolated_home / "taolu.db")
    raw.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION + 1}")
    raw.close()
    with pytest.raises(RuntimeError, match="升级"):
        db.connect()
