# leetcode-coach（taolu · 套路）

LeetCode 刷题教练：把每道题落到一个“套路”上，用分层提示逼自己先想，
再把[灵茶山艾府](https://leetcode.cn/u/endlesscheng/)的解法拆成“为什么这么想”，最后用间隔复习记牢套路。

形态是 **Claude Code 插件 + 本地 Python 核心**：插件提供 slash command，
状态（做到第几层提示、复习排期）由本地 CLI 和 SQLite 持有。

> 状态：M2（解法拆解 explain）。可用：套路卡、题目元数据、`/taolu:coach` 提示梯、`/taolu:explain` 解法拆解；review 还在路上。
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

然后在会话里：

- `/taolu:card 单调栈`：查看套路卡
- `/taolu:coach 739`：开始（或接着）做 739 题，按 L0–L4 分层提示辅导
- `/taolu:explain 739`：拆解灵神的解法（要求先做完或放弃这道题，或推进到 L4）

### 分层提示（coach）

进度存在 SQLite 里，模型每一轮先问 CLI“现在允许讲到哪一层”，不靠自己记。
**门禁在 CLI 里**：L2 之前输出里不会出现套路名、卡片 id，L3 之前不会出现模板。

| 层 | 内容 |
|---|---|
| L0 | 复述题意，从数据范围反推目标复杂度 |
| L1 | 引导性问题，不说套路名 |
| L2 | 套路名 + 一句关键观察 |
| L3 | 模板骨架，关键 1–3 行留空 |
| L4 | 完整思路与 Python 解法 |

进入下一层前要先写一句自己的想法（`--note`）；坚持跳过用 `--skip`，会记为“看了提示”。

直接用命令行也可以（`uv run taolu ...`）：

```bash
taolu problem add 1004 max-consecutive-ones-iii "最大连续1的个数 III" Medium   # 追加题目元数据
taolu session start 739                  # 开始，L0；同一时间只能有一个进行中的练习
taolu session state [--json]             # 当前层级与允许透露的内容
taolu session advance --note "想法"      # 或 --skip；进入下一层，最高 L4
taolu session end --ac                   # 或 --no-ac；打印小结（层数、跳过数、耗时）
taolu session abandon                    # 放弃，不计 AC
```

`taolu session state` 只用于读状态；`taolu card show`、`taolu problem show --reveal` 会剧透，做题时别用。

### 解法拆解（explain）与本地缓存

`/taolu:explain <题号>`：你把灵神的解法**贴进来**（只给链接的话，链接只作为来源记录，不会被抓取），
Claude 按固定 7 段输出：套路归属、关键观察、怎么想到、与模板的差异、易错点、Python 版、同套路下一题。

**题解和笔记只存本地**：`~/.taolu/solutions/<题号>/solution-<n>.md` 和 `~/.taolu/notes/<题号>.md`
（`TAOLU_HOME` 可改位置，但不允许指到仓库目录里）。它们不进仓库、不进数据库。

门禁：正在做某题且没到 L4 时，这道题的 `explain context / explain show / solution show` 一律拒绝（会剧透）；做别的题不受影响。

```bash
taolu solution save 739 --lang go --source URL [--file PATH]   # 不给 --file 读 stdin
taolu solution list [739]                  # 不打印正文
taolu solution show 739 [--n 1]
taolu explain context 739 --json           # 题目、题解、关联卡与模板、同套路下一题、旧笔记
taolu explain save 739 [--file PATH]       # 覆盖前保留 .bak
taolu explain show 739
taolu card link 739 monotonic-stack        # 只改卡片 frontmatter 的 problems 行
```

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
