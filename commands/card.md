---
description: 查看一张套路卡（不带参数则列出全部）
argument-hint: "[卡片 id 或名称，如 滑动窗口]"
allowed-tools: Bash(uv run:*)
---
用 Bash 运行下面的命令，原样展示输出，不要补充或改写卡片内容：

- 如果参数 `$ARGUMENTS` 为空：`uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" taolu card list`
- 否则：`uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" taolu card show $ARGUMENTS`

命令报错时，把错误信息告诉我，不要自己编一张卡。
