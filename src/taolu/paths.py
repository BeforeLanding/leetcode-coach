"""路径解析。

- 内容（套路卡、题目元数据）随仓库走，默认在仓库根目录的 cards/ 与 data/。
- 状态（SQLite）是个人数据，默认在 ~/.taolu/，绝不进仓库。
两者都可用环境变量覆盖，测试里靠这个隔离。
"""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def content_root() -> Path:
    return Path(os.environ.get("TAOLU_CONTENT", _REPO_ROOT))


def cards_dir() -> Path:
    return content_root() / "cards"


def problems_csv() -> Path:
    return content_root() / "data" / "problems.csv"


def home() -> Path:
    return Path(os.environ.get("TAOLU_HOME", Path.home() / ".taolu"))


def db_path() -> Path:
    return home() / "taolu.db"


def solutions_dir() -> Path:
    """用户粘贴的题解缓存。版权边界：只能在 home() 下，绝不进仓库。"""
    return _private("solutions")


def notes_dir() -> Path:
    """生成的拆解笔记，同样只在本地。"""
    return _private("notes")


def _private(name: str) -> Path:
    d = home().resolve()
    root = content_root().resolve()
    if d == root or root in d.parents:
        raise RuntimeError(f"TAOLU_HOME（{d}）不能在仓库目录内：题解和笔记不能进仓库")
    return d / name
