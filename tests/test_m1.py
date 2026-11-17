import json
import sqlite3

import pytest

from taolu import cards, cli, db, paths, sessions

# 739 每日温度 → 单调栈卡。标题里不含卡片名，门禁测试才有意义。
PID = "739"


def run(capsys, *argv):
    code = cli.main(list(argv))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def state(capsys):
    code, out, err = run(capsys, "session", "state", "--json")
    assert code == 0, err
    return json.loads(out), out


def advance_to(capsys, n):
    """再推进 n 层（每层带一条 note）。"""
    for i in range(n):
        assert run(capsys, "session", "advance", "--note", f"想法{i}")[0] == 0


# ---- 迁移 ----

def make_v1_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(path)
    raw.executescript(db.SCHEMA_V1)
    raw.execute("INSERT INTO problem (id, slug, title, difficulty) VALUES (739, 'daily-temperatures', '每日温度', 'Medium')")
    raw.execute("INSERT INTO attempt (problem_id, started_at, max_hint_level, accepted) VALUES (739, '2026-01-01T00:00:00+00:00', 2, 1)")
    raw.execute("PRAGMA user_version = 1")
    raw.commit()
    raw.close()


def test_v1_database_migrates_to_v2_without_losing_data(isolated_home):
    make_v1_db(isolated_home / "taolu.db")
    conn = db.connect()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION == 2
    row = conn.execute("SELECT problem_id, max_hint_level, accepted FROM attempt").fetchone()
    assert tuple(row) == (739, 2, 1)
    assert conn.execute("SELECT title FROM problem WHERE id = 739").fetchone()[0] == "每日温度"
    assert conn.execute("SELECT COUNT(*) FROM attempt_step").fetchone()[0] == 0


def test_fresh_database_reaches_latest_version(isolated_home):
    assert db.connect().execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_migration_is_idempotent(isolated_home):
    db.connect().close()
    assert db.connect().execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_failed_migration_rolls_back(isolated_home, monkeypatch):
    make_v1_db(isolated_home / "taolu.db")

    def boom(conn):
        conn.execute("CREATE TABLE half_done (x)")
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "MIGRATIONS", [db._migrate_to_v1, boom])
    monkeypatch.setattr(db, "SCHEMA_VERSION", 2)
    with pytest.raises(RuntimeError, match="boom"):
        db.connect()
    raw = sqlite3.connect(isolated_home / "taolu.db")
    assert raw.execute("PRAGMA user_version").fetchone()[0] == 1
    assert raw.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 'half_done'").fetchone()[0] == 0


# ---- start / 单一进行中 ----

def test_start_unknown_problem_hints_problem_add(capsys):
    code, _, err = run(capsys, "session", "start", "99999")
    assert code == 1 and "problem add" in err


def test_only_one_active_attempt(capsys):
    assert run(capsys, "session", "start", PID)[0] == 0
    code, _, err = run(capsys, "session", "start", "1")
    assert code == 1 and "end" in err and "abandon" in err


def test_database_itself_rejects_second_active_attempt():
    conn = db.connect()
    conn.execute("INSERT INTO problem (id, slug, title, difficulty) VALUES (1, 'a', 'a', 'Easy')")
    conn.execute("INSERT INTO attempt (problem_id, started_at) VALUES (1, 'x')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO attempt (problem_id, started_at) VALUES (1, 'y')")


def test_can_start_again_after_end(capsys):
    run(capsys, "session", "start", PID)
    run(capsys, "session", "end", "--no-ac")
    assert run(capsys, "session", "start", PID)[0] == 0


def test_state_without_active_attempt_fails_readably(capsys):
    code, out, err = run(capsys, "session", "state", "--json")
    assert code == 1 and out == "" and "没有进行中" in err


# ---- advance ----

def test_advance_requires_exactly_one_of_note_or_skip(capsys):
    run(capsys, "session", "start", PID)
    with pytest.raises(SystemExit):
        cli.main(["session", "advance"])
    with pytest.raises(SystemExit):
        cli.main(["session", "advance", "--note", "x", "--skip"])
    capsys.readouterr()
    assert state(capsys)[0]["level"] == 0
    code, _, err = run(capsys, "session", "advance", "--note", "   ")
    assert code == 1 and "不能为空" in err


def test_advance_records_notes_and_skips_and_caps_at_4(capsys):
    run(capsys, "session", "start", PID)
    run(capsys, "session", "advance", "--note", "n=1e5，要 O(n)")
    run(capsys, "session", "advance", "--skip")
    advance_to(capsys, 2)
    st, _ = state(capsys)
    assert st["level"] == 4
    assert [(n["level"], n["note"], n["skipped"]) for n in st["notes"]] == [
        (0, "n=1e5，要 O(n)", False),
        (1, None, True),
        (2, "想法0", False),
        (3, "想法1", False),
    ]
    code, _, err = run(capsys, "session", "advance", "--note", "再来")
    assert code == 1 and "最高层" in err
    assert state(capsys)[0]["level"] == 4


# ---- 门禁：这是 M1 的核心验收 ----

@pytest.mark.parametrize("level", [0, 1])
@pytest.mark.parametrize("as_json", [True, False])
def test_gate_hides_card_before_l2(capsys, level, as_json):
    run(capsys, "session", "start", PID)
    advance_to(capsys, level)
    argv = ["session", "state"] + (["--json"] if as_json else [])
    code, out, _ = run(capsys, *argv)
    assert code == 0
    for leak in ("单调栈", "monotonic-stack", "next_greater", "signals", "栈"):
        assert leak not in out, f"L{level} 泄露了 {leak!r}"
    if as_json:
        assert json.loads(out)["reveal"] == {"cards": None, "template": None}


@pytest.mark.parametrize("as_json", [True, False])
def test_gate_l2_shows_card_but_not_template(capsys, as_json):
    run(capsys, "session", "start", PID)
    advance_to(capsys, 2)
    argv = ["session", "state"] + (["--json"] if as_json else [])
    _, out, _ = run(capsys, *argv)
    assert "单调栈" in out and "monotonic-stack" in out
    assert "next_greater" not in out and "def " not in out
    if as_json:
        reveal = json.loads(out)["reveal"]
        assert reveal["cards"][0]["signals"]
        assert reveal["template"] is None


@pytest.mark.parametrize("level", [3, 4])
def test_gate_l3_and_l4_show_template(capsys, level):
    run(capsys, "session", "start", PID)
    advance_to(capsys, level)
    template = state(capsys)[0]["reveal"]["template"]
    assert "def next_greater" in template and "```" not in template


def test_gate_across_every_repo_problem(capsys):
    """仓库里每道挂了卡的题：L0/L1 都不能出现它自己的卡片名/id。"""
    for c in cards.load_dir(paths.cards_dir()):
        for pid in c.problems:
            run(capsys, "session", "start", str(pid))
            for _ in range(2):
                _, out, _ = run(capsys, "session", "state", "--json")
                prob = json.loads(out)["problem"]
                # 题目自己的标题和 URL 是公开元数据，可能恰好含套路词（704 的标题/slug），不算泄露
                scrubbed = out.replace(prob["title"], "").replace(prob["url"], "")
                assert c.id not in scrubbed and c.name not in scrubbed, (pid, c.id)
                run(capsys, "session", "advance", "--skip")
            run(capsys, "session", "abandon")


def test_problem_without_card_at_l3(capsys, content):
    (content / "cards" / "a.md").write_text(
        "---\nid: a\nname: 甲\ncategory: t\nproblems: [1]\n---\n```python\npass\n```\n", encoding="utf-8"
    )
    run(capsys, "session", "start", "3")
    advance_to(capsys, 3)
    assert state(capsys)[0]["reveal"] == {"cards": [], "template": None}


# ---- 模板抽取 ----

def test_extract_template_takes_first_python_block():
    body = "说明\n```text\nno\n```\n```python\na = 1\n```\n```python\nb = 2\n```\n"
    assert cards.extract_template(body) == "a = 1\n"
    assert cards.extract_template("没有代码") is None
    assert cards.extract_template("```python\n没闭合") is None


# ---- end / abandon ----

def test_end_ac_summary(capsys):
    run(capsys, "session", "start", PID)
    run(capsys, "session", "advance", "--note", "想法")
    run(capsys, "session", "advance", "--skip")
    code, out, _ = run(capsys, "session", "end", "--ac")
    assert code == 0
    assert "739. 每日温度" in out and "结果：AC" in out
    assert "用了 2 层提示" in out and "跳过 1 层" in out and "耗时：" in out
    row = db.connect().execute("SELECT accepted, ended_at FROM attempt").fetchone()
    assert row["accepted"] == 1 and row["ended_at"]


def test_end_no_ac_and_flag_required(capsys):
    run(capsys, "session", "start", PID)
    with pytest.raises(SystemExit):
        cli.main(["session", "end"])
    capsys.readouterr()
    _, out, _ = run(capsys, "session", "end", "--no-ac")
    assert "结果：未 AC" in out
    assert db.connect().execute("SELECT accepted FROM attempt").fetchone()[0] == 0


def test_abandon_leaves_accepted_null(capsys):
    run(capsys, "session", "start", PID)
    _, out, _ = run(capsys, "session", "abandon")
    assert "放弃" in out
    row = db.connect().execute("SELECT accepted, ended_at FROM attempt").fetchone()
    assert row["accepted"] is None and row["ended_at"]
    assert run(capsys, "session", "state")[0] == 1


def test_summary_duration_uses_timestamps(capsys):
    run(capsys, "session", "start", PID)
    conn = db.connect()
    conn.execute("UPDATE attempt SET started_at = '2000-01-01T00:00:00+00:00'")
    conn.commit()
    assert "小时" in sessions.finish(conn, True)


# ---- problem add ----

def test_problem_add_appends_and_is_usable(capsys, content):
    code, out, _ = run(capsys, "problem", "add", "42", "trapping-rain-water", "接雨水, 双指针", "Hard")
    assert code == 0 and "已添加" in out
    text = (content / "data" / "problems.csv").read_text(encoding="utf-8")
    assert text.endswith('42,trapping-rain-water,"接雨水, 双指针",Hard,\n')
    assert run(capsys, "session", "start", "42")[0] == 0


def test_problem_add_duplicate_id_and_slug(capsys, content):
    f = content / "data" / "problems.csv"
    before = f.read_text(encoding="utf-8")
    code, _, err = run(capsys, "problem", "add", "1", "other", "x", "Easy")
    assert code == 1 and "已存在" in err
    code, _, err = run(capsys, "problem", "add", "2", "two-sum", "x", "Easy")
    assert code == 1 and "slug" in err
    assert f.read_text(encoding="utf-8") == before


def test_problem_add_rejects_bad_difficulty(content):
    with pytest.raises(SystemExit):
        cli.main(["problem", "add", "5", "x", "x", "Super"])


def test_problem_add_handles_missing_trailing_newline(capsys, content):
    f = content / "data" / "problems.csv"
    f.write_bytes(f.read_bytes().rstrip(b"\n"))
    assert run(capsys, "problem", "add", "5", "x", "x", "Easy")[0] == 0
    assert len(f.read_text(encoding="utf-8").splitlines()) == 4
