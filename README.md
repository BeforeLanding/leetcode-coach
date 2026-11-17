# leetcode-coach（taolu · 套路）

LeetCode 刷题教练：把每道题落到一个“套路”上，用分层提示逼自己先想，
再把[灵茶山艾府](https://leetcode.cn/u/endlesscheng/)的解法拆成“为什么这么想”，最后用间隔复习记牢套路。

形态是 **Claude Code 插件 + 本地 Python 核心**：插件提供 slash command，
状态（做到第几层提示、复习排期）由本地 CLI 和 SQLite 持有。

> 状态：M0（骨架）。目前可用的是套路卡和题目元数据，coach / explain / review 还在路上。
> 完整方案见 [docs/00-plan.md](docs/00-plan.md)。

## 安装与使用

需要 Python ≥ 3.12 和 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run taolu init                 # 初始化 ~/.taolu/taolu.db，同步题目与套路卡
uv run taolu card list
uv run taolu card show 滑动窗口    # id、名称或唯一子串都行
uv run taolu problem show 739     # 默认不显示所属套路，加 --reveal 才显示
```

作为 Claude Code 插件本地加载：

```bash
claude --plugin-dir /path/to/leetcode-coach
```

然后在会话里用 `/taolu:card 单调栈`。

## 目录

| 路径 | 内容 |
|---|---|
| `cards/` | 套路卡（Markdown + frontmatter），本项目的核心内容 |
| `data/problems.csv` | 题目元数据：题号、slug、标题、难度、难度分 |
| `src/taolu/` | CLI 与存储 |
| `commands/` | Claude Code 插件命令 |
| `docs/` | 方案与设计文档 |

## 内容与版权

- 本仓库**不包含**任何题面全文或灵茶山艾府的题解正文，只有题号级元数据和指向原文的链接。
- `cards/` 里的讲解与模板是作者自己的学习笔记。思路受灵茶山艾府公开题解与题单启发，在此致谢；如需原文请访问其力扣主页。
- 做题时粘贴的题解只缓存在本地（`~/.taolu/`），不会进入仓库。

## 开发

```bash
uv run pytest
```
