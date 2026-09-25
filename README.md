# uCore-Tutorial-Code

Course project for THU-OS.

课程过程记录：在当前实验分支的仓库根目录运行 `python3 course.py`，先自动初始化 AI 会话归档，再安装 VS Code 记录插件并打开实验工作区与实时日志。安装要求、日志位置和日常命令见 [实验过程记录说明](docs/course-recording.md)。

AI 过程记录：启动时默认使用 `auto`，可通过 `python3 course.py --agent codex` 指定客户端；也支持 `claude`、`cursor`、`vscode`、`copilot`、`opencode` 和 `all`。会话以 JSONL 保存到 `.ai/agent-sessions/<agent>/`，文件名包含日期时间。`.ai/agent-sessions/`、`.ai/events/` 和 `.ai/submissions/` 的全部内容可随实验代码一起提交。请同学们不要改动或删除这些记录，提交时会检查这些记录作为考核参考。详细设置见 [AI 会话归档说明](docs/agent-session-archive.md)。

**Codex 首次使用需要信任 hooks**：安装后，在实验仓库根目录运行 `codex`，输入 `/hooks`，找到 `ucore-session-archive` 的 `Stop` 和 `SessionEnd`，分别审阅并选择 **Trust（信任）**。信任后才会自动归档。使用 VS Code Codex 的同学还需重载窗口并新建会话；更新插件后，如提示 hooks 发生变化，请重新审阅并信任。

main 和各实验分支均提供 `course.py` 及完整运行依赖；安装一次后，切换到 `ch1`–`ch8` 仍会记录。实验分支可运行 `git course logs` 查看日志，运行 `git agent-plugins auto` 再次配置 AI 归档。迁移来源和验证方式见 [记录工具功能说明](docs/course-monitor-report.md)。

对标 [rCore-Tutorial-v3](https://github.com/rcore-os/rCore-Tutorial-v3/) 的 C 版本代码。

主要参考 [xv6-riscv](https://github.com/mit-pdos/xv6-riscv), [uCore-SMP](https://github.com/TianhuaTao/uCore-SMP)。

实验 lab1-lab5 基准代码分别位于 ch3-ch8　分支下。

实验在线文档[uCore-Tutorial-Guide](https://learningos.cn/uCore-Tutorial-Guide/)。

注：主分支 `main` 用于分发课程说明与记录工具，实验代码位于章节分支。完成课程实验时，请在 clone 仓库后先 push `main` 分支到清华 Git，随后可直接在自己开发所需的章节分支运行 `python3 course.py` 完成记录配置。

## 记录脚本更新

已同步 `course-tool` 的 `6d68289` 版本，支持 `--project` 和 OpenCode。
已有安装需在当前分支拉取更新后重新运行 `python3 course.py`；OpenCode 用户运行 `python3 course.py --agent opencode`。
仅更新运行文件时使用 `python3 course.py install --skip-extension`，再用 `git agent-plugins <客户端>` 刷新客户端 hooks。
运行副本跨章节使用；三类过程记录随代码提交，本地运行文件与客户端配置继续忽略。详见 [记录说明](docs/course-recording.md)。
