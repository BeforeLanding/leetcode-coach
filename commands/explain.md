---
description: 拆解一道题的灵神解法（套路归属、关键观察、怎么想到、Python 版）
argument-hint: "<题号，如 739>"
allowed-tools: Bash(uv run:*), Skill
---
先加载 `taolu:explain-format` skill，按它规定的 7 段固定格式输出。本命令负责取材料和存取，题号是 `$ARGUMENTS`（为空就让我给出，不要猜）。

CLI 前缀固定为 `uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" taolu`，下面简写为 `taolu`，执行时必须写全。

1. 运行 `taolu explain context $ARGUMENTS --json`。
   - 被拒绝（我正在做这道题且没到 L4）：把错误原文转告我，**停下**，不要想办法绕过（不要去读 `~/.taolu` 下的文件，不要改状态）。
   - 题库里没有这道题：转告报错，并提示可以用 `taolu problem add <题号> <slug> <标题> <Easy|Medium|Hard>` 添加。
2. `solutions` 为空：请我粘贴灵神的解法正文，并附上来源链接（可选）、语言（go/python/cpp/java/other）。
   **不要自己去抓取 leetcode.cn 页面**；我只给了链接时，请我把正文贴进来，链接只作为 `--source` 记录。
   拿到后用 heredoc 传给 CLI（`'EOF'` 的引号不能省，防止 `$` 和反引号被 shell 展开）：
   ```
   taolu solution save <题号> --lang <语言> --source "<链接，没有就省略这个参数>" <<'EOF'
   <我贴的正文，原样>
   EOF
   ```
   存好后重新运行 `explain context --json`。
3. `existing_note` 不为 null：先问我是直接看旧笔记，还是重新生成。选旧笔记就原样展示并结束；选重新生成才继续。
4. 按 `explain-format` skill 写拆解，紧扣 `solutions` 里我缓存的那份解法（有多份时问我用哪份，默认最新一份）。
   写完先展示给我，再用 heredoc 保存：
   ```
   taolu explain save <题号> <<'EOF'
   <完整的拆解 Markdown>
   EOF
   ```
5. 如果拆解里判断出的套路不在 `cards` 里，但 `taolu card list` 里有对应的卡：**问我**要不要运行 `taolu card link <题号> <卡片 id>`，**不要自己执行**。

题解和笔记只存本机 `~/.taolu/`，不会进仓库。任何命令报错都把原文告诉我，不要自己编内容。
