"""本地题解缓存：<home>/solutions/<题号>/solution-<n>.md。

版权边界：题解正文是用户从别处粘贴的，只能存在 paths.home() 之下，不进仓库、不进数据库。
这里是纯文件缓存，文件头是受限 frontmatter（source / lang / saved_at）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from taolu import paths

LANGS = ("go", "python", "cpp", "java", "other")
_NAME = re.compile(r"^solution-(\d+)\.md$")


@dataclass(frozen=True)
class Solution:
    n: int
    lang: str
    source: str
    saved_at: str
    text: str


def _dir(problem_id: int) -> Path:
    return paths.solutions_dir() / str(problem_id)


def _numbers(d: Path) -> list[int]:
    if not d.is_dir():
        return []
    return sorted(int(m.group(1)) for p in d.iterdir() if (m := _NAME.match(p.name)))


def save(problem_id: int, text: str, *, source: str = "", lang: str = "other") -> int:
    if not text.strip():
        raise ValueError("题解内容为空：请通过 --file 或 stdin 提供正文")
    if lang not in LANGS:
        raise ValueError(f"--lang 必须是 {'/'.join(LANGS)}")
    source = source.strip()
    if "\n" in source or "\r" in source:
        raise ValueError("--source 不能包含换行")
    d = _dir(problem_id)
    d.mkdir(parents=True, exist_ok=True)
    n = (_numbers(d) or [0])[-1] + 1
    saved_at = datetime.now(UTC).isoformat(timespec="seconds")
    head = f"---\nsource: {source}\nlang: {lang}\nsaved_at: {saved_at}\n---\n"
    body = text.replace("\r\n", "\n").rstrip("\n") + "\n"
    (d / f"solution-{n}.md").write_text(head + body, encoding="utf-8", newline="\n")
    return n


def _parse(path: Path, n: int) -> Solution:
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError(f"{path}: 缓存文件头损坏")
    end = lines.index("---", 1)
    meta = {}
    for line in lines[1:end]:
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return Solution(
        n=n,
        lang=meta.get("lang", "other"),
        source=meta.get("source", ""),
        saved_at=meta.get("saved_at", ""),
        text="\n".join(lines[end + 1 :]),
    )


def list_for(problem_id: int) -> list[Solution]:
    d = _dir(problem_id)
    return [_parse(d / f"solution-{n}.md", n) for n in _numbers(d)]


def problems_with_solutions() -> list[int]:
    root = paths.solutions_dir()
    if not root.is_dir():
        return []
    return sorted(int(p.name) for p in root.iterdir() if p.name.isdigit() and _numbers(p))


def get(problem_id: int, n: int | None = None) -> Solution:
    items = list_for(problem_id)
    if not items:
        raise LookupError(f"{problem_id} 号题还没有缓存题解，先用 `taolu solution save {problem_id}`")
    if n is None:
        return items[-1]
    for s in items:
        if s.n == n:
            return s
    raise LookupError(f"{problem_id} 号题没有第 {n} 份题解（已有 {', '.join(str(s.n) for s in items)}）")
