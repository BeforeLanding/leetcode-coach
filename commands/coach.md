---
description: 开始或继续一道题的分层提示辅导
argument-hint: "<题号，如 739>"
allowed-tools: Bash(uv run:*), Skill
---
先加载 `taolu:coach-protocol` skill，并严格按它的协议辅导。本命令只负责定位会话：

1. 运行 `uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" taolu session state --json`。
2. 如果成功（已有进行中的会话）：
   - 参数 `$ARGUMENTS` 为空，或等于该会话的题号：直接接着这个会话继续，告诉我当前在哪一层。
   - 参数是另一道题：先告诉我正在做哪道题、在哪一层，问我是继续、结束（AC / 没 AC）还是放弃；**不要自己决定**，也不要自动放弃。
3. 如果失败（没有进行中的会话）：
   - 参数为空：让我给出题号，不要猜。
   - 否则运行 `uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" taolu session start $ARGUMENTS`。
     题库里没有这道题时，把报错转告我，并提示可以用
     `taolu problem add <题号> <slug> <标题> <Easy|Medium|Hard>` 添加（我会给你 slug 和标题，你再替我运行）。
4. 开始或接上之后，重新运行 `session state --json`，按当前层级开始辅导。

任何命令报错，都把错误原文告诉我，不要自己编状态。
