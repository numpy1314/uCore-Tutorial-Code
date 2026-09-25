# 实验过程记录工具功能说明

本功能于 2026-09-11 从 `rCore-Tutorial-Code` 的 `main` 分支最近两个提交移植，
适配 uCore 的 C 实验代码与 `ch1`–`ch8` 章节分支：

| 源提交 | 迁移能力 |
| --- | --- |
| `112d9ea8de8a09c37382f25f5c05947d35a2ce41` | 课程入口、VS Code 插件、实时日志、AI 事件适配、提交快照、四种 Agent 会话归档、配置、文档和回归测试 |
| `1e99bee21e5b04297ffb059f6c91fc6deac886bb` | 在 Git 本地排除规则中忽略所有层级的 Python 缓存，避免切换章节后出现未跟踪文件 |

直接来源为 `rCore-Tutorial-Code`；其工具最初来自
[numpy1314/tg-rcore-tutorial](https://github.com/numpy1314/tg-rcore-tutorial) 的
`2d0f165`、`5d64228`、`1e2722f`、`1afdf2c`。
迁移工具保留其 [GPL-3.0 许可证](../.course-monitor/licenses/course-tools-GPL-3.0.txt)，
Rewind 组件保留 [MIT 许可证](../.course-monitor/licenses/Rewind-MIT.txt)。

本次将插件与 marketplace 分别命名为 `ucore-session-archive` 和 `ucore-tutorial-code`，
Cursor / Copilot 的运行脚本使用 `ucore-hooks` 目录，避免与 rCore 的插件安装冲突。
示例和集成测试使用 `os/main.c`；Dev Container 提供 C/RISC-V 工具链。
随仓库分发的 VSIX 保持来源版本不变，其课程采集接口支持 C 文件。

## 功能清单

| 功能 | 当前实现 |
| --- | --- |
| VS Code 文件操作 | 打开、关闭、编辑、保存、新建、重命名和删除 |
| 终端与 Tasks | 命令、任务的开始和结束，退出码、耗时；终端依赖 Shell Integration |
| 实时查看 | Windows 独立日志窗口，Linux/macOS 终端持续查看 |
| 课程 AI 操作 | Codex 单次调用的 Prompt、会话边界、命令结果、文件操作 |
| 显式 AI 接入 | Python、Shell、PowerShell、Node.js 入口以及扩展事件接口 |
| 完整会话归档 | Codex、Claude Code、Cursor、VS Code Copilot |
| 归档模式 | messages、tool-calls、full，按 Agent 独立配置 |
| JSONL 文件 | `.ai/agent-sessions/<agent>/<UTC日期时间>_<session-id>.jsonl`，同一会话持续更新同一文件 |
| 提交快照 | 预提交 Hook 导出并暂存增量事件，按当前暂存区的事件 ID 去重 |
| 随代码提交 | main/ch1–ch8 放行 `.ai/agent-sessions/`、`.ai/events/` 和 `.ai/submissions/`，普通 `git add` 即可暂存 |
| 开关与恢复 | 保留已有日志和模式；课程配置重载后生效，归档配置每次 hook 读取 |
| 容器 | main 提供 Dev Container 初始化与连接后的插件安装入口 |
| 跨分支使用 | 任一实验分支安装一次，切换 ch1–ch8 后继续记录 |

## 任一实验分支安装，跨分支使用

main 和各实验分支均提供源码、配置示例和插件安装包。安装器将运行文件放到本地
`.ai/course-tools/`，建立 `git course` 和 `git agent-plugins` 入口，并设置稳定的提交 Hook。
工具运行文件、IDE 状态及 Agent 配置的本地排除规则写入 Git 的 `info/exclude`，
切换章节后仍然生效。重新安装会清理旧版本对课程记录的排除规则。

VS Code 扩展读取已安装的课程配置。Codex、Claude Code 的插件源也指向本地运行副本。
Agent 项目配置、Cursor hooks 和 Copilot hooks 都作为本地文件保留。
Copilot 使用 `.github/hooks/ucore-session-archive.json` 及课程工作区中的设置，章节原有的
`.vscode/settings.json` 保持原样。默认 hook 发现位置见 [VS Code 官方说明](https://code.visualstudio.com/docs/agent-customization/hooks#hook-file-locations)。

课程事件保存在 `.ai/events/`，提交检查点保存在 `.ai/submissions/`，会话正文保存在
`.ai/agent-sessions/`。安装过程从目标仓库开始生成记录。

## 验证

```sh
python3 -m unittest discover -s plugins/ucore-session-archive/tests
python3 -m unittest discover -s tests
bash -n scripts/setup-agent-plugins.sh
```

归档回归测试覆盖四种 Agent、模式过滤、重复事件、完整 JSONL、失败恢复和配置保留。
跨分支测试在隔离仓库安装工具后切换 main/ch1–ch8，验证运行文件、Git 入口、课程事件、
四种 Agent 的归档、普通 `git add .` 暂存三类记录和真实提交 Hook；同时检查安装器不会创建或改写章节的编辑器设置，
并保留用户已有的 C/C++ 设置。
VS Code 事件通过安装包中的课程适配器与编辑器接口替身验证。
Agent CLI 的安装、课程 Codex 调用和归档事件通过模拟客户端与合成会话验证。

真实 Agent 客户端、Windows 图形窗口、VS Code 的界面交互和 Dev Container 构建
仍需在对应环境中验收。
实验内核的构建与测试由章节自己的流程负责。

使用方法见 [实验过程记录](course-recording.md) 和 [AI 会话归档](agent-session-archive.md)。


## 2026-09-25 工具同步

本仓库的 main 和各实验分支均提供同步自 [leeehh/course-tool](https://github.com/leeehh/course-tool) 的工具，版本 `6d68289f601a76b51f33efed3ad13198ae57a579`。
在本仓库运行 `python3 course.py` 仍会安装到本仓库；也可用 `--project` 指定其他 Git 项目。
安装后的 `git course` 和 `git agent-plugins` 使用 `.ai/course-tools/`，可跨全部章节分支运行。
升级时在当前分支拉取更新，再运行 `python3 course.py`（或指定 `--agent`）；原记录和配置会保留。
插件仍使用原有 `ucore-session-archive@ucore-tutorial-code` 标识，避免已有配置另起一套插件。

本次同步增加 OpenCode 归档、外部项目安装及记录忽略规则迁移。保留实验源码、运行验收脚本和现有记录。
