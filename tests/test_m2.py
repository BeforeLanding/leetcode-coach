import io
import json
import sys

import pytest

from taolu import cards, cli, db, paths

# 全部是自己编的假代码，不是任何真实题解
FAKE_GO = "// 假的 Go 解法\nfunc f(a []int) int { return len(a) } // 中文注释：栈\n"
PID = "739"  # 每日温度 → 单调栈卡


def run(capsys, *argv, stdin=None, monkeypatch=None):
    if stdin is not None:
        raw = io.BytesIO(stdin.encode("utf-8"))
        # 模拟 Windows 默认的 GBK 控制台：不 reconfigure 就会读成乱码
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(raw, encoding="gbk"))
    code = cli.main(list(argv))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): p.stat().st_mtime_ns
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


# ---- solution ----

def test_solution_save_from_stdin_chinese_and_show(capsys, monkeypatch):
    code, out, err = run(capsys, "solution", "save", PID, "--lang", "go", "--source", "https://example.com/x",
                         stdin=FAKE_GO, monkeypatch=monkeypatch)
    assert code == 0, err
    code, out, _ = run(capsys, "solution", "show", PID)
    assert code == 0 and out == FAKE_GO


def test_solution_stdin_bom_is_stripped(capsys, monkeypatch):
    run(capsys, "solution", "save", PID, stdin="﻿代码\n", monkeypatch=monkeypatch)
    assert run(capsys, "solution", "show", PID)[1] == "代码\n"


def test_solution_multiple_and_list_hides_body(capsys, monkeypatch, tmp_path):
    run(capsys, "solution", "save", PID, "--lang", "go", "--source", "https://a", stdin="第一份\n", monkeypatch=monkeypatch)
    f = tmp_path / "s2.txt"
    f.write_text("第二份\n", encoding="utf-8")
    run(capsys, "solution", "save", PID, "--lang", "python", "--file", str(f))
    _, out, _ = run(capsys, "solution", "list", PID)
    assert "#1 · go · https://a" in out and "#2 · python" in out
    assert "第一份" not in out and "第二份" not in out
    assert run(capsys, "solution", "show", PID)[1] == "第二份\n"
    assert run(capsys, "solution", "show", PID, "--n", "1")[1] == "第一份\n"
    code, _, err = run(capsys, "solution", "show", PID, "--n", "9")
    assert code == 1 and "没有第 9 份" in err
    assert "739 #1" in run(capsys, "solution", "list")[1]


def test_solution_rejects_empty_and_unknown_problem(capsys, monkeypatch):
    code, _, err = run(capsys, "solution", "save", PID, stdin="  \n", monkeypatch=monkeypatch)
    assert code == 1 and "为空" in err
    code, _, err = run(capsys, "solution", "save", "99999", stdin="x", monkeypatch=monkeypatch)
    assert code == 1 and "problem add" in err
    code, _, err = run(capsys, "solution", "show", PID)
    assert code == 1 and "还没有缓存" in err


def test_solution_body_starting_with_dashes_survives(capsys, monkeypatch):
    run(capsys, "solution", "save", PID, stdin="---\n正文里的分隔线\n", monkeypatch=monkeypatch)
    assert run(capsys, "solution", "show", PID)[1] == "---\n正文里的分隔线\n"


# ---- 版权边界：仓库零写入 ----

def test_nothing_written_into_content_root(capsys, monkeypatch, content, isolated_home):
    (content / "cards" / "a.md").write_text(
        "---\nid: a\nname: 甲\ncategory: t\nproblems: [1]\n---\n```python\npass\n```\n", encoding="utf-8"
    )
    run(capsys, "init")  # init 只写数据库，不写内容目录
    before = snapshot(content)
    run(capsys, "solution", "save", "1", "--lang", "go", stdin=FAKE_GO, monkeypatch=monkeypatch)
    run(capsys, "explain", "save", "1", stdin="# 笔记\n", monkeypatch=monkeypatch)
    run(capsys, "explain", "save", "1", stdin="# 笔记 v2\n", monkeypatch=monkeypatch)
    run(capsys, "explain", "context", "1", "--json")
    assert snapshot(content) == before
    assert (isolated_home / "solutions" / "1" / "solution-1.md").exists()
    assert (isolated_home / "notes" / "1.md").exists()


def test_home_inside_repo_is_refused(monkeypatch, content):
    monkeypatch.setenv("TAOLU_HOME", str(content / "inside"))
    with pytest.raises(RuntimeError, match="不能在仓库目录内"):
        paths.solutions_dir()


# ---- explain context 与门禁 ----

def ctx(capsys):
    code, out, err = run(capsys, "explain", "context", PID, "--json")
    return code, (json.loads(out) if code == 0 else None), err


def test_context_shape_without_solutions(capsys):
    code, c, _ = ctx(capsys)
    assert code == 0
    assert c["problem"]["id"] == 739 and c["solutions"] == [] and c["existing_note"] is None
    assert c["cards"][0]["id"] == "monotonic-stack" and "def next_greater" in c["cards"][0]["template"]


def test_context_includes_solutions_and_note(capsys, monkeypatch):
    run(capsys, "solution", "save", PID, "--lang", "go", "--source", "https://s", stdin=FAKE_GO, monkeypatch=monkeypatch)
    run(capsys, "explain", "save", PID, stdin="# 拆解\n", monkeypatch=monkeypatch)
    _, c, _ = ctx(capsys)
    assert c["solutions"] == [{"n": 1, "lang": "go", "source": "https://s", "text": FAKE_GO}]
    assert c["existing_note"] == "# 拆解\n"


@pytest.mark.parametrize("level", [0, 1, 2, 3])
def test_explain_refused_while_coaching_below_l4(capsys, level):
    run(capsys, "session", "start", PID)
    for i in range(level):
        run(capsys, "session", "advance", "--note", f"n{i}")
    code, out, err = run(capsys, "explain", "context", PID, "--json")
    assert code == 1 and out == "" and "L4" in err and "放弃" in err
    for argv in (("explain", "show", PID), ("solution", "show", PID)):
        assert run(capsys, *argv)[0] == 1


def test_explain_allowed_at_l4_and_after_end(capsys):
    run(capsys, "session", "start", PID)
    for i in range(4):
        run(capsys, "session", "advance", "--skip")
    assert ctx(capsys)[0] == 0
    run(capsys, "session", "abandon")
    assert ctx(capsys)[0] == 0


def test_explain_allowed_when_coaching_another_problem(capsys):
    run(capsys, "session", "start", "496")
    assert ctx(capsys)[0] == 0


def test_explain_unknown_problem(capsys):
    code, _, err = run(capsys, "explain", "context", "99999", "--json")
    assert code == 1 and "problem add" in err


# ---- next_candidates ----

def accept(pid):
    conn = db.connect()
    conn.execute(
        "INSERT INTO attempt (problem_id, started_at, ended_at, accepted) VALUES (?, 'a', 'b', 1)", (pid,)
    )
    conn.commit()


def test_next_candidates_cap_order_and_exclusions(capsys):
    cli.main(["init"])
    capsys.readouterr()
    _, c, _ = ctx(capsys)
    # 单调栈卡顺序 [739, 496, 503, 84, 42]：排除当前题 739，最多 3 道
    assert [p["id"] for p in c["next_candidates"][0]["problems"]] == [496, 503, 84]
    accept(496)
    assert [p["id"] for p in ctx(capsys)[1]["next_candidates"][0]["problems"]] == [503, 84, 42]
    # 未 AC（accepted=0 / NULL）的不算 AC
    conn = db.connect()
    conn.execute("INSERT INTO attempt (problem_id, started_at, ended_at, accepted) VALUES (503, 'a', 'b', 0)")
    conn.execute("INSERT INTO attempt (problem_id, started_at, ended_at) VALUES (84, 'a', 'b')")
    conn.commit()
    assert [p["id"] for p in ctx(capsys)[1]["next_candidates"][0]["problems"]] == [503, 84, 42]
    for pid in (503, 84, 42):
        accept(pid)
    assert ctx(capsys)[1]["next_candidates"][0]["problems"] == []


# ---- explain save / show ----

def test_explain_save_keeps_bak_on_overwrite(capsys, monkeypatch, isolated_home):
    run(capsys, "explain", "save", PID, stdin="旧笔记\n", monkeypatch=monkeypatch)
    notes = isolated_home / "notes"
    assert not (notes / "739.md.bak").exists()
    run(capsys, "explain", "save", PID, stdin="新笔记\n", monkeypatch=monkeypatch)
    assert (notes / "739.md").read_text(encoding="utf-8") == "新笔记\n"
    assert (notes / "739.md.bak").read_text(encoding="utf-8") == "旧笔记\n"
    assert run(capsys, "explain", "show", PID)[1] == "新笔记\n"


def test_explain_show_without_note_and_empty_save(capsys, monkeypatch):
    code, _, err = run(capsys, "explain", "show", PID)
    assert code == 1 and "还没有拆解笔记" in err
    code, _, err = run(capsys, "explain", "save", PID, stdin="\n", monkeypatch=monkeypatch)
    assert code == 1 and "为空" in err


# ---- card link ----

CARD_LF = "---\nid: a\nname: 甲\ncategory: 测试\nsignals: [x, y]\nproblems: [1]\n---\n正文，含 problems: [9] 字样\n\n```python\npass\n```\n"


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
def test_card_link_changes_only_the_problems_line(capsys, content, eol):
    original = CARD_LF.replace("\n", eol).encode("utf-8")
    path = content / "cards" / "a.md"
    path.write_bytes(original)
    code, _, err = run(capsys, "card", "link", "3", "a")
    assert code == 0, err
    new = path.read_bytes()
    old_lines = original.decode().splitlines(keepends=True)
    new_lines = new.decode().splitlines(keepends=True)
    assert len(old_lines) == len(new_lines)
    diff = [(o, n) for o, n in zip(old_lines, new_lines) if o != n]
    assert diff == [(f"problems: [1]{eol}", f"problems: [1, 3]{eol}")]
    assert cards.parse(path).problems == [1, 3]


def test_card_link_empty_list_and_errors(capsys, content):
    path = content / "cards" / "a.md"
    path.write_text("---\nid: a\nname: 甲\ncategory: t\nproblems: []\n---\n正文\n", encoding="utf-8")
    assert run(capsys, "card", "link", "1", "a")[0] == 0
    assert "problems: [1]\n" in path.read_text(encoding="utf-8")
    snap = path.read_bytes()
    code, _, err = run(capsys, "card", "link", "1", "a")
    assert code == 1 and "已经关联" in err
    code, _, err = run(capsys, "card", "link", "3", "nope")
    assert code == 1 and "找不到卡片" in err
    code, _, err = run(capsys, "card", "link", "999", "a")
    assert code == 1 and "problem add" in err
    assert path.read_bytes() == snap
