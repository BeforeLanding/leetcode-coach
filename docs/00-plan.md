# taolu（套路）— LeetCode 刷题教练 · 方案 v0

> 一句话：把每道题落到一个“套路”上，用分层提示逼自己先想，再用灵茶山艾府（下称灵神）的解法讲清“为什么这么想”，最后用间隔复习把套路记牢。

日期：2026-11-17 · 状态：形态已定（Claude Code 插件 + 本地 Python），M0 开工

## 决策记录
- 2026-11-17：形态定为 **Claude Code 插件 + 本地 Python 核心**；Web 应用推迟到 v1 之后。
- 2026-11-17（默认假设，可改）：名字用 `taolu`；仓库先按“可公开”的标准组织（题解正文不进仓库）；灵神解法由我手动粘贴或给链接，仅本地缓存。
- Python 核心零第三方运行时依赖（argparse + sqlite3 + 标准库），开发依赖只有 pytest，用 uv 管理。
- 2026-11-17（M1）：提示梯状态机落在 CLI + SQLite。`attempt.max_hint_level` 即当前层；新增 `attempt_step(attempt_id, level, note, skipped, at)` 记录每层的想法/跳过（schema v2，`db.MIGRATIONS` 逐级迁移，每级一个事务）。
- 2026-11-17（M1）：“同一时间最多一个进行中的 attempt”除了 CLI 检查，还用 `UNIQUE INDEX ON attempt((1)) WHERE ended_at IS NULL` 在库层兜底。
- 2026-11-17（M1）：门禁只在 `sessions.state` 里算：L<2 `reveal.cards = null`，L<3 `reveal.template = null`；文本与 JSON 输出共用同一份数据，均有测试。题目自己的标题/URL 是公开元数据，可能含套路词（如 704 二分查找），不算泄露。题挂多张卡时，模板取排在最前的一张。
- 2026-11-17（M1）：`advance` 在 L4 再调用报错而不是静默吞掉；`note` 与 `skip` 二选一，空 note 拒绝。放弃 = `ended_at` 有值且 `accepted IS NULL`。
- 2026-11-17（M1）：插件调用 CLI 统一用 `uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" taolu ...`。官方文档：该变量在 command/skill 的 Markdown 正文里被**内联替换**，但**不会**导出到 Bash 工具的环境变量，所以命令必须写在正文里（不能写成 `$CLAUDE_PLUGIN_ROOT` 让 shell 去取）。Windows 上替换结果多为正斜杠路径。实机验证见汇报。

---

## 1. 为什么做

| 痛点 | 现状 | taolu 的做法 |
|---|---|---|
| 刷得快、忘得快 | 做完就过，一周后同类题还是不会 | 题目挂到“套路卡”，按 FSRS 间隔复习套路而不是单题 |
| 灵神解法短，看懂“怎么写”但不懂“怎么想到” | 代码很精炼，关键观察常在一句话里 | 把解法拆成：约束→复杂度→关键观察→套路模板→与模板的差异 |
| 一卡住就看题解 | 没有中间态，要么全靠自己要么直接看答案 | 分层提示梯（L0–L4），每层之间留出自己尝试的空间 |
| 不知道下一题刷什么 | 随机刷或按热题 | 跟灵神分类题单的顺序 + 难度分，按掌握度推荐下一题 |

目标用户就是我自己：用 Python，面向面试（见 `interview-algorithms` 仓库），参考灵神题单入门。

## 2. 项目名

**taolu（套路）** —— 推荐。
- 直指核心理念：灵神的讲解本质是把题归约到少数套路（枚举右维护左、二分答案、单调栈……）。
- 短、好记、命令好打：`taolu coach 42`、`/taolu:review`。
- 不用灵神本人的名字/ID 做产品名，避免让人误以为是官方或背书。

备选：`hintladder`（突出分层提示）、`tidan`（题单）、`endless-coach`（致敬 EndlessCheng，但同样有“像官方”的问题）。

## 3. 产品形态（推荐 + 备选）

**推荐：Claude Code 插件 + 本地 Python 核心**
- 前端就是 Claude Code：`/taolu:coach <题号>`、`/taolu:explain`、`/taolu:review`、`/taolu:next`。
- 本地 Python 包 `taolu`：题目元数据、套路卡、进度（SQLite）、FSRS 调度、提示梯状态机；插件的 skill 调它的 CLI。
- 理由：我本来就在 Claude Code 里刷题和写代码；做过 dsh-done-check / dsh-catchup，插件链路熟；无 UI 成本，MVP 一两周可用。

备选：独立 Web 应用（FastAPI + 前端 + Claude API）。展示性更强，但 UI 会吃掉大半时间，放到 v1 之后再议。

## 4. 核心功能（MVP）

### F1 分层提示梯 `coach <题号>`
| 层 | 内容 | 是否透露套路名 |
|---|---|---|
| L0 | 题意重述 + 从数据范围反推目标复杂度（n≤1e5 → O(n log n)） | 否 |
| L1 | 方向性提问（“如果固定右端点，左端点需要满足什么？”） | 否 |
| L2 | 点出套路名 + 关键观察一句话 | 是 |
| L3 | 伪代码 / 模板骨架，留关键行空白 | 是 |
| L4 | 灵神解法讲解（见 F2） | 是 |

- 每层之间要求我先写一句想法或代码再继续（可 `--skip` 强行跳过，但会记为“看了提示”，影响复习评分）。
- 我贴代码时：只指出错在哪一类（边界/复杂度/思路），不直接给正确代码，除非已到 L4。

### F2 灵神解法拆解 `explain <题号>`
输入：我提供的灵神解法（链接或粘贴，见 §6）。输出固定结构：
1. **套路归属**：落到哪张套路卡（可多张）。
2. **关键观察**：一句话，“为什么能这么做”。
3. **怎么想到**：从约束/题目特征 → 套路的推理链。
4. **与模板的差异**：模板代码 vs 本题代码的 diff，标出改动的那几行及原因。
5. **易错点**：边界、初始化、溢出、开闭区间。
6. **Python 版**：灵神原解若是 Go/其他语言，给等价 Python 写法（我自己的复习材料，不外发）。
7. **同套路下一题**：从题单里挑 1–2 道。

### F3 套路卡库
- 每张卡：名称、适用信号（题面关键词/约束特征）、Python 模板、关键不变量、典型题 3–5 道、易错点。
- 初始 ~25 张，按灵神分类题单的大类组织：滑动窗口与双指针、二分、单调栈、网格图、位运算、图论、动态规划、常用数据结构（前缀和/堆/并查集/树状数组）、数学、贪心、链表/二叉树/回溯、字符串。
- 卡片内容由我 + Claude 撰写，是自己的笔记，不是复制题解。

### F4 进度与复习 `review` / `next`
- 每次做题记录：题号、套路卡、用到的最高提示层、是否 AC、耗时。
- 复习对象是**套路卡**（单题挂在卡下）：评分由“最高提示层 + 是否独立 AC”自动折算，用 FSRS 排期。
- `review`：今日到期的卡 → 随机抽卡下一道没做过/做错过的题，只给题面，计时自测。
- `next`：按题单顺序 + 难度分 + 薄弱卡推荐。

## 5. 非目标（v0 不做）
- 自动登录/提交 LeetCode、抓取账号做题记录。
- 爬取或镜像灵神题解全文。
- 多语言（只做 Python）。
- Web UI、多用户、排行榜。

## 6. 数据来源与版权边界
| 数据 | 来源 | 处理方式 |
|---|---|---|
| 题目元数据（题号、标题、难度、标签） | 公开 API / 手工 | 只存元数据和链接，不存题面全文 |
| 难度分 | zerotrac 公开的周赛题目难度分数据 | 存分数，注明出处（许可证待核实） |
| 灵神分类题单的题目顺序 | 灵神在 leetcode.cn 的公开题单 | 只存“题号 + 所属分类 + 顺序”这类事实，附原帖链接 |
| 灵神解法正文 | 我做题时手动粘贴或在浏览器里打开 | **只在本地缓存，供个人学习；仓库与公开内容中不包含**；`.gitignore` 掉缓存目录 |
| 灵神 GitHub `EndlessCheng/codeforces-go` | 公开仓库 | 引用前先核实许可证；默认只链接不复制 |

如果项目以后公开（作品集），公开部分只有：代码、我自己写的套路卡、题号级元数据、指向原文的链接。

## 7. 架构草图

```
Claude Code
  └─ plugin: taolu
       ├─ commands/  coach · explain · review · next · card
       ├─ skills/    coach-protocol（提示梯规则、不剧透约束）
       │             explain-format（F2 的固定输出结构）
       └─ 调用 → taolu CLI（Python）
                   ├─ problems    题目元数据 + 题单顺序 + 难度分
                   ├─ cards       套路卡（Markdown + YAML frontmatter，进 git）
                   ├─ sessions    提示梯状态机，记录每层停留
                   ├─ scheduler   FSRS
                   └─ store       SQLite（~/.taolu/taolu.db，不进 git）
```

关键设计点：
- **LLM 只负责讲解，状态由 CLI 持有**：当前在第几层、看过什么、评分多少都在 SQLite，避免模型“记错进度”或一次吐完答案。
- **不剧透是硬约束**：coach skill 每一轮先调 `taolu session state` 拿到允许透露的层级，再生成内容。
- **套路卡是纯文本**：Markdown 进 git，方便手改和 diff，也是作品集里最能体现理解的部分。

## 8. 数据模型（初稿）
- `problem(id, slug, title, difficulty, rating, url)`
- `list_entry(list_name, section, order, problem_id)`
- `card(id, name, file_path)`；`problem_card(problem_id, card_id)`
- `attempt(id, problem_id, started_at, ended_at, max_hint_level, accepted, notes)`
- `card_review(card_id, due, stability, difficulty, reps, lapses, last_review)`（FSRS 状态）

## 9. 里程碑
| 里程碑 | 内容 | 验收 |
|---|---|---|
| M0 骨架（2–3 天） | Python 包 + SQLite + 题目元数据导入 + 5 张套路卡 | `taolu card show 滑动窗口` 可用 |
| M1 coach（3–4 天，已实现，真实会话下的 10 题自测待做） | 提示梯状态机 + 插件 coach 命令 | 用 10 道题自测：未到 L2 前从未出现套路名或代码 |
| M2 explain（2–3 天） | F2 固定结构输出 + 套路卡关联 | 10 道灵神题解拆解，结构完整、Python 版能 AC |
| M3 review/next（3 天） | FSRS + 推荐 | 连用一周，每天 review 能出到期卡 |
| M4 打磨 | 卡片补到 ~25 张、README、演示 | 自己每天在用 |

范围纪律：先 M0–M2 跑通“做一道题”的完整闭环再碰复习；语法边界和花哨推荐算法都往后放。

## 10. 待你确认
~~形态~~ 已定为插件 + 本地 Python。其余三项目前按“决策记录”里的默认假设推进：
1. 项目名 `taolu`。
2. 是否公开成作品集——仓库先按可公开标准组织，是否真正推上 GitHub 之后再定。
3. 灵神解法：手动粘贴/给链接、仅本地缓存。
