from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """每个测试用独立的数据库，绝不碰 ~/.taolu。"""
    monkeypatch.setenv("TAOLU_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("TAOLU_CONTENT", raising=False)
    return tmp_path / "home"


@pytest.fixture
def content(tmp_path, monkeypatch):
    """一份最小的临时内容目录，用于测试错误路径。"""
    root = tmp_path / "content"
    (root / "cards").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "data" / "problems.csv").write_text(
        "id,slug,title,difficulty,rating\n1,two-sum,两数之和,Easy,\n3,lswrc,无重复,Medium,1500\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TAOLU_CONTENT", str(root))
    return root
