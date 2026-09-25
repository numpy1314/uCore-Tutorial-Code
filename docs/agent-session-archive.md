# Agent 会话本地归档

本项目提供 `ucore-session-archive`，支持 Codex、Claude Code、Cursor、VS Code
GitHub Copilot 和 OpenCode 的本地会话归档。会话按归档模式保存，便于回顾实验过程和后续处理。

会话保存在目标项目的 `.ai/agent-sessions/`，文件名带 UTC 日期时间和会话 ID：

```text
.ai/agent-sessions/
├── codex/2026-09-09_14-30-00_<session-id>.jsonl
├── claude-code/2026-09-09_14-30-00_<session-id>.jsonl
├── cursor/2026-09-09_14-30-00_<conversation-id>.jsonl
├── vscode-copilot/2026-09-09_14-30-00_<session-id>.jsonl
└── opencode/2026-09-09_14-30-00_<session-id>.jsonl
```

同一会话始终更新同一个文件，重复 hooks 不新增会话文件。日期使用首次可用的会话
时间；源记录没有时间时使用首次归档时间。后续源记录重放或模式切换不会改变文件名。
整个目录（包括 `.state/` 归档索引）可通过普通 `git add` 随实验代码提交，
安装器会为目标项目当前分支添加放行规则。客户端的源会话日志不会被修改或删除。

## 安装

统一入口需要 Python 3.10+。在工具仓库执行：

```bash
python3 course.py --project /path/to/my-lab
python3 course.py --project /path/to/my-lab --agent codex
```

启动会先调用归档配置脚本，再打开课程工作区与实时日志。`--agent` 支持
`auto`、`codex`、`claude`、`cursor`、`vscode`、`copilot`、`opencode` 和 `all`，默认 `auto`。

独立归档脚本需要 Bash、Python 3.9+ 和对应客户端。也可以单独配置：

```bash
# 自动检测 PATH 中的客户端
./scripts/setup-agent-plugins.sh auto --project /path/to/my-lab

# 指定客户端；copilot 是 vscode 的别名
./scripts/setup-agent-plugins.sh codex --project /path/to/my-lab
./scripts/setup-agent-plugins.sh claude --project /path/to/my-lab
./scripts/setup-agent-plugins.sh cursor --project /path/to/my-lab --mode full
./scripts/setup-agent-plugins.sh vscode --project /path/to/my-lab
./scripts/setup-agent-plugins.sh opencode --project /path/to/my-lab

# 配置所有 Agent，需要 Codex 和 Claude Code CLI 均已安装
./scripts/setup-agent-plugins.sh all --project /path/to/my-lab
```

安装后，在目标项目内使用 `git agent-plugins auto` 或 `git agent-plugins codex`。
工具运行副本保存在该项目的 `.ai/course-tools/`，切换分支后继续使用；新的分支运行一次
安装命令即可补充记录放行规则。更新时从新版工具源码再次安装，已有开关与模式会保留。

只装图形界面时可显式选择 `cursor`、`vscode` 或 `opencode`，脚本不安装 Agent 客户端。
Windows 建议使用 WSL；Remote SSH、WSL、容器中在项目所在环境执行。
也可直接使用 Python 入口：

```bash
python3 plugins/ucore-session-archive/scripts/setup_agents.py cursor --project /path/to/my-lab
```

Codex / Claude Code 从 `.ai/course-tools/` 的本地 marketplace 安装归档插件，在用户级配置中关闭该插件，
在项目级配置中启用。实际项目设置为本地文件，切换分支后继续保留；工具仓库提供对应示例。
重新执行脚本会刷新本插件的缓存。Claude Code 安装后重新启动或执行 `/reload-plugins`。

Cursor / Copilot 使用原生项目 hooks，运行脚本分别安装到
`.cursor/ucore-hooks/` 和 `.vscode/ucore-hooks/`。Copilot 的 hook 配置位于
`.github/hooks/ucore-session-archive.json`，对应设置放在 `.ai/ide/course.code-workspace`，
保留目标项目原有的 VS Code 设置。Cursor 用 **Open Folder** 单独打开并信任本项目；
Copilot 打开上述课程工作区，再新建 Agent 对话。已有窗口可重新加载。
Cursor 查看 **Output → Hooks**，Copilot 查看 **Output → Copilot Chat Hooks**。

OpenCode 使用[项目本地插件](https://opencode.ai/docs/plugins/)，安装到
`.opencode/plugins/ucore-session-archive.js`，归档脚本位于 `.opencode/ucore-hooks/`。
安装后在目标项目重新启动 OpenCode 即可，无需额外 npm 依赖。插件在读取会话正文前检查
当前目录与会话所属目录，只归档本项目的会话；不会修改全局 OpenCode 配置或其他插件。

## 每个 Agent 的配置

| Agent | 目标项目中的本地配置 | 工具仓库中的示例 |
| --- | --- | --- |
| Codex | `.codex/session-archive.json` | `.codex/session-archive.example.json` |
| Claude Code | `.claude/session-archive.json` | `.claude/session-archive.example.json` |
| Cursor | `.cursor/session-archive.json` | `.cursor/session-archive.example.json` |
| VS Code Copilot | `.vscode/session-archive.json` | `.vscode/session-archive.example.json` |
| OpenCode | `.opencode/session-archive.json` | `.opencode/session-archive.example.json` |

各客户端使用相同格式，互不读取其他 Agent 的设置：

```json
{
  "enabled": true,
  "mode": "messages"
}
```

| mode | 保存内容 |
| --- | --- |
| `messages` | 用户输入和 Agent 最终回答；首次安装默认值 |
| `tool-calls` | 在 messages 基础上增加工具名、调用 ID 和工具输入，不含工具输出 |
| `full` | 增加可取得的中间消息、可读推理记录和工具结果 |

`enabled: false` 暂停归档，已有文件保留。每次 hook 都重新读取配置；配置文件缺失、
JSON 无效或 enabled 不是布尔值 true 时不归档；无效的 mode 回退到 messages。
安装脚本会拒绝无效配置，重复安装保留原来的 enabled 和 mode；`--mode` 只覆盖 mode。
本地配置被 Git 忽略。

归档按最近的当前 Agent 项目配置确定归属，不依赖仓库名字。从项目子目录触发的 hooks
也可以找到总仓库的配置；子目录有独立配置时以子目录配置为准，包括其停用设置。
编辑器仍应从总仓库根目录打开，以便发现项目 hooks。

## JSONL 格式

使用 UTF-8，每行一个独立 JSON 对象。首行是版本化会话信息，后续是按模式过滤的统一
事件记录，保留消息字符串及结构化参数。字符串内部的换行按 JSON 规则转义，读取后
可以原样恢复。示例：

```jsonl
{"type":"session","schema_version":1,"agent":"codex","session_id":"example","started_at":"2026-09-09T14:30:00+00:00","mode":"messages"}
{"type":"message","role":"user","content":"请解释启动流程","turn":1}
{"type":"message","role":"assistant","content":"内核从入口开始执行。","turn":1}
```

事件类型包括 `message`、`intermediate`、`reasoning`、`tool_call`、`tool_result`。
`content` 可以是字符串或原客户端的内容块数组；工具输入保存在 `input` / `arguments`
等请求字段，工具结果通过 `call_id` 关联。记录有可用时间时保留 `timestamp`。
Cursor / Copilot 额外保存稳定的 `event_id` 供回调去重。
OpenCode 2.x 保存 `message_id` 和内容序号，以便更新当前上下文并保留压缩前已归档的消息。

图片、音频等二进制内容只保留引用或附件描述，省略内嵌数据和不透明加密字段。
归档采用统一事件结构，并按 mode 过滤内容。
以下命令逐行读取一个文件：

```bash
python3 - /path/to/session.jsonl <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as source:
    for line in source:
        print(json.loads(line))
PY
```

## 刷新与恢复

Codex / Claude Code 在 `Stop`、`SessionEnd` 刷新会话。Claude 的 Stop 回复尚未写进
transcript 时，会从 hook 的最终回复字段补全并去重。

OpenCode 2.x 使用默认导出的 `id` / `setup` 插件，在执行成功、失败、中断及压缩结束时
刷新归档；已在 2.0.11 验证。1.x 使用 `server` 入口及 `session.idle` / `session.error` 回调。
2.x 的会话 API 只返回压缩后的活动上下文，插件保留此前已归档的消息；提高 mode 无法
恢复已经被压缩且此前未保存的内容。重复回调更新同一文件，强制退出后需等后续回调补全。

Cursor 按事件采集；提升 mode 无法恢复此前丢弃的内容。Copilot 读取客户端提供的
v1 transcript，提升 mode 可以恢复已纳入归档轮次中仍存在于源文件的内容。降低 mode
会在活动会话的下一次 hook 中移除不再允许保存的内容，已结束会话不会自动重写。

Cursor / Copilot 在对应 Agent 目录的 `.state/<session-id>.sqlite3` 保存排序、ID、哈希
和时间索引，索引不保存对话正文。备份时将 `.state` 与 JSONL 一起保留；索引丢失时
插件会保留已有归档并报错。所有正文只在 JSONL 文件中保存。

归档使用临时文件和原子替换，POSIX 文件权限为 600、归档目录为 700。跟踪实时更新可用
`tail -F <文件>`。源文件损坏时保留上次归档；hook 失败不会阻止 Agent 正常结束回答。
Copilot 的 v1 transcript 属于客户端内部格式，版本不支持或最终回复尚未写完时会提示
并等待后续 hook；进程被直接终止且没有后续回调时，最后一段未落盘内容无法保证恢复。

本功能与 `git course` 的 `.ai/events/` 实验操作日志独立。`git course codex` 使用
临时会话模式；需要本插件的完整会话归档时，从项目根目录直接启动普通 Codex 会话。

## 验证

```bash
python3 -m unittest discover -s plugins/ucore-session-archive/tests
bash -n scripts/setup-agent-plugins.sh
```

测试使用临时目录、合成 transcript 和模拟客户端命令。
首次在真实客户端启用后，完成一次含工具调用和最终回答的会话，检查 JSONL 内容与模式
是否符合预期。
