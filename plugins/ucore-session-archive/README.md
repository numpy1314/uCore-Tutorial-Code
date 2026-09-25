# Course Session Archive

Codex、Claude Code、Cursor、VS Code GitHub Copilot 和 OpenCode 的项目会话归档插件。
插件名称为 `ucore-session-archive`，本地插件源为 `course-tool`。

在工具仓库根目录运行，显式选择目标 Git 项目：

```sh
./scripts/setup-agent-plugins.sh auto --project /path/to/my-lab
./scripts/setup-agent-plugins.sh cursor --project /path/to/my-lab --mode full
./scripts/setup-agent-plugins.sh opencode --project /path/to/my-lab
```

也可使用统一入口 `python3 course.py --project /path/to/my-lab --agent codex`。
安装后，在目标项目中通过 `git agent-plugins <agent>` 再次配置。

运行程序安装到目标项目 `.ai/course-tools/`，会话保存到
`.ai/agent-sessions/<agent>/<UTC日期时间>_<session-id>.jsonl`。
归档文件与 `.state/` 索引可以随项目代码提交。
各 Agent 的 `session-archive.json` 支持独立的 `enabled` 开关与
`messages`、`tool-calls`、`full` 三种模式。

完整说明见 [AI 会话归档](../../docs/agent-session-archive.md)。
