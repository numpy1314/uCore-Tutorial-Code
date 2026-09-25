# 课程过程记录

本仓库在 `main` 分发同步自 [leeehh/course-tool](https://github.com/leeehh/course-tool) 的工具，版本 `6d68289f601a76b51f33efed3ad13198ae57a579`。
在本仓库运行 `python3 course.py` 仍会安装到本仓库；也可用 `--project` 指定其他 Git 项目。
安装后的 `git course` 和 `git agent-plugins` 使用 `.ai/course-tools/`，可跨全部章节分支运行。
升级时先在 `main` 拉取更新，再运行 `python3 course.py`（或指定 `--agent`）；原记录和配置会保留。
插件仍使用原有 `ucore-session-archive@ucore-tutorial-code` 标识，避免已有配置另起一套插件。

`course-tool` 为任意已有 Git 项目提供操作记录。工具仓库负责分发，目标项目保存运行副本、
配置和课堂记录，不需要把工具源文件合并进实验代码。

## 安装与启动

需要 Python 3.10+、Git 和 Bash。打开工作区及安装扩展需要 VS Code 1.93+ 和 `code` 命令。
在远程开发、WSL 或容器中，应在目标项目所在环境执行命令。

```sh
python3 /path/to/course-tool/course.py --project /path/to/my-lab
python3 /path/to/course-tool/course.py start --project /path/to/my-lab --agent codex --skip-extension
```

默认动作是 `start`：先调用 `scripts/setup-agent-plugins.sh`，使用 `--agent` 选择的客户端
初始化会话归档，再安装课程扩展与提交 Hook，打开 `.ai/ide/course.code-workspace` 及实时日志。
`--skip-extension` 只跳过扩展安装；`start` 仍会打开 VS Code。

`--agent` 默认 `auto`，支持 `codex`、`claude`、`cursor`、`vscode`、`copilot`、`opencode`、`all`。
`--agent codex` 用于选择归档客户端；位置参数 `codex` 用于发起一次课程 Codex 调用。

只安装记录工具、不打开编辑器时使用：

```sh
python3 /path/to/course-tool/course.py install --project /path/to/my-lab --skip-extension
```

`install` 独立安装课程工具；AI 客户端可通过 `start` 或下面的脚本配置：

```sh
/path/to/course-tool/scripts/setup-agent-plugins.sh cursor --project /path/to/my-lab --mode full
```

`--project` 可以指定项目根目录或子目录。从项目内运行外部工具时，没有随仓库分发工具副本时，省略该参数会识别当前
Git 项目；已安装的 `git course` 始终默认使用其运行副本所属的项目。在工具源码目录内执行
时需显式选择项目，避免把工具仓库当作实验。

## 日常命令

以下命令在目标项目中执行：

| 命令 | 用途 |
| --- | --- |
| `git course` | 自动配置 AI 归档并打开课程工作区、实时日志 |
| `git course --agent cursor` | 启动并选择 Cursor 归档 |
| `git course status` | 检查记录开关、项目路径、日志与 Hook |
| `git course logs` | 查看已有日志并持续显示新事件 |
| `git course install --skip-extension` | 更新当前分支的记录规则和 Hook |
| `git course codex` | 发起一次只读 Codex 调用并记录问题、操作事件 |
| `git course codex --allow-edits` | 允许这次 Codex 调用修改项目文件 |
| `git course export` | 手动生成事件快照，不会暂存或提交 |
| `git agent-plugins codex` | 单独更新指定 Agent 的配置 |

外部源码入口同样支持 `status`、`logs`、`codex`、`export`，均通过 `--project` 访问目标
项目安装的运行副本。尚未安装时会提示先安装。

## 记录内容

在受信任的课程工作区打开、修改并保存一个项目文件，日志会显示文件打开、编辑、保存等
操作。VS Code 集成终端支持 Shell Integration 时还可记录命令开始、结束、退出码和耗时；
Tasks 接口记录任务开始与结束。`.ai/`、`.git/`、构建缓存和凭据文件不作为文件操作采集目标。

课程事件只保存允许的元数据，配置默认不保存代码正文和终端输出。AI 操作来自显式适配器，
不根据文件改动猜测是否由 AI 生成。Agent 会话正文由独立归档插件按 mode 保存，详见
[会话归档说明](agent-session-archive.md)。

其他客户端可将一个 JSON 事件写到已安装的适配器标准输入：

```sh
printf '%s\n' '{"type":"ai_prompt","prompt":"解释项目结构","tool":"my-client"}' | \
  python3 /path/to/my-lab/.ai/course-tools/.course-monitor/ai-ingest.py
```

同目录还提供 Shell、PowerShell 和 Node.js 包装入口。这些记录脚本应从目标项目的运行副本
调用；源码目录中的脚本不代替目标项目安装。

## 保存与提交

所有下列路径都相对于目标项目根目录：

| 路径 | 内容 |
| --- | --- |
| `.ai/events/` | VS Code 和课程 AI 入口生成的 JSONL 事件 |
| `.ai/agent-sessions/<agent>/` | JSONL 会话归档与 `.state/` 索引 |
| `.ai/submissions/` | 增量事件快照 |
| `.ai/ide/` | 工作区文件和日志查看状态 |
| `.ai/course-tools/` | 本地运行文件与配置 |

前三个目录的全部内容可以通过普通 `git add` 暂存。安装器将放行规则写到当前分支的
`.gitignore`；如存在 `.ai/.gitignore`，也会追加相应规则。已有规则会保留。
工具运行文件、IDE 状态、Agent 项目设置通过 Git 的 `info/exclude` 保持本地忽略。
旧版对课程记录的本地排除项会被清理。

```sh
git add .
git commit -m "docs: record lab work"
git push origin HEAD
```

提交 Hook 会额外导出并暂存尚未提交的课程事件，按暂存区中的事件 ID 去重。
反复手动 `export` 而未暂存上次快照时，同一事件可能再次导出。
请保留完整课堂记录，便于回顾实验过程。

## 分支、更新与配置保留

工具没有固定分支列表。安装后的运行副本和 Git 入口可以继续在其他分支使用。
切换前先提交当前分支的记录；在尚未包含放行规则的分支执行 `git course install --skip-extension`
或正常 `git course`，然后提交新增的 `.gitignore` 规则。

更新工具时，从新版源码执行带 `--project` 的安装命令。已有记录、课程配置和 Agent 归档
开关与模式都会保留。每个 clone / worktree 使用自己的 `.ai/course-tools/`，需要各自安装。

课程配置位于 `.ai/course-tools/.course-monitor/config.json`。设置 `enabled: false`
会暂停课程操作记录，修改后重载 VS Code；Agent 归档的开关单独设置。
安装器保留项目原有 `.vscode/settings.json`，课程专用设置写入课程工作区。
存在其他 `core.hooksPath` 或 pre-commit Hook 时，安装器会保留并提示先整合。

## 检查问题

- 找不到 `git course`：对当前 checkout 执行一次外部安装命令。
- 文件事件缺失：确认工作区受信任、扩展已启用、课程配置的 `enabled` 为 `true`。
- 终端事件缺失：新建集成终端并确认 Shell Integration 已启用。
- AI 会话缺失：检查对应 Agent 配置和 hooks，并完成一轮问答。
- 记录没有出现在 Git 中：在当前分支重装放行规则，用 `git check-ignore -v <文件>` 查看生效规则。
