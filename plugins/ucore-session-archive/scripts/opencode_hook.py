#!/usr/bin/env python3
"""Archive a project-scoped OpenCode SDK session snapshot."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from archive_session import (
    archive_session_id, find_project_root, prepare_archive_directory,
    read_archive_config, sanitize_content, session_archive_path, session_header,
)
from archive_storage import atomic_write, private_directory


def scoped_directory(value, root):
    if not isinstance(value, str) or not Path(value).is_absolute():
        return False
    directory = Path(value).resolve()
    return (directory == root or root in directory.parents) and find_project_root(str(directory), "opencode") == root


def timestamp(milliseconds):
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, (int, float)):
        raise ValueError("missing OpenCode timestamp")
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).isoformat()


def events(messages, session_id, mode, root):
    """Use SDK message/part identities, not display text, to distinguish turns."""
    turns = {}
    seen = set()
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("info"), dict):
            raise ValueError("invalid OpenCode message")
        info, parts = message["info"], message.get("parts")
        mid = info.get("id")
        if (not isinstance(mid, str) or not mid or mid in seen
                or info.get("sessionID") != session_id or not isinstance(parts, list)
                or info.get("role") not in {"user", "assistant"}):
            raise ValueError("invalid OpenCode message identity")
        seen.add(mid)
        role = info["role"]
        if role == "assistant" and not scoped_directory(info.get("path", {}).get("cwd"), root):
            raise ValueError("OpenCode message is outside this project")
        if role == "user":
            turns[mid] = len(turns) + 1
        turn = turns.get(mid if role == "user" else info.get("parentID"), len(turns) or 1)
        stamp = timestamp(info.get("time", {}).get("created"))
        final = (role == "assistant" and info.get("time", {}).get("completed") is not None
                 and info.get("finish") not in {None, "tool-calls", "unknown"}
                 and not info.get("summary") and not info.get("error"))
        part_ids = set()
        for part in parts:
            if (not isinstance(part, dict) or not isinstance(part.get("id"), str)
                    or part["id"] in part_ids or part.get("messageID") != mid
                    or part.get("sessionID") != session_id):
                raise ValueError("invalid OpenCode part identity")
            part_ids.add(part["id"])
            kind = part.get("type")
            event = None
            if kind == "text" and not part.get("ignored"):
                if not isinstance(part.get("text"), str):
                    raise ValueError("invalid OpenCode text")
                is_message = (role == "user" and not part.get("synthetic")) or final
                if is_message or mode == "full":
                    event = {"type": "message" if is_message else "intermediate",
                             "role": role, "content": part["text"]}
            elif kind == "file" and role == "user":
                attachment = {"type": "attachment", "kind": part.get("mime", "file")}
                for key in ("filename", "url"):
                    value = part.get(key)
                    if isinstance(value, str) and not value.startswith("data:"):
                        attachment[key] = value
                event = {"type": "message", "role": "user", "content": [attachment]}
            elif kind == "reasoning" and mode == "full":
                if not isinstance(part.get("text"), str):
                    raise ValueError("invalid OpenCode reasoning")
                event = {"type": "reasoning", "content": part["text"]}
            elif kind == "tool" and mode != "messages":
                state = part.get("state")
                if (not isinstance(state, dict) or not isinstance(state.get("input"), dict)
                        or state.get("status") not in {"pending", "running", "completed", "error"}
                        or not isinstance(part.get("callID"), str) or not isinstance(part.get("tool"), str)):
                    raise ValueError("invalid OpenCode tool state")
                yield {"type": "tool_call", "name": part["tool"], "call_id": part["callID"],
                       "input": state["input"], "turn": turn, "timestamp": stamp}
                if mode == "full" and state["status"] in {"completed", "error"}:
                    error = state["status"] == "error"
                    content = state.get("error" if error else "output")
                    if not isinstance(content, str):
                        raise ValueError("invalid OpenCode tool result")
                    event = {"type": "tool_result", "call_id": part["callID"],
                             "content": content, "is_error": error}
            if event is not None:
                yield {**event, "turn": turn, "timestamp": stamp}


def attachment(value):
    """OpenCode 2 attachments carry raw base64 separately from their references."""
    result = {"type": "attachment", "kind": value.get("mime", "file")}
    source = value.get("source", {})
    for key, item in (("filename", value.get("name")), ("url", value.get("uri", source.get("uri")))):
        if isinstance(item, str) and not item.startswith("data:"):
            result[key] = item
    return result


def v2_events(messages, root):
    """Normalize the public 2.x SessionMessage union; never copy provider state."""
    seen = set()
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("invalid OpenCode 2 message")
        mid = message.get("id")
        if not isinstance(mid, str) or not mid or mid in seen:
            raise ValueError("invalid OpenCode 2 message identity")
        seen.add(mid)
        stamp = timestamp(message.get("time", {}).get("created"))
        kind = message.get("type")
        entries = []
        if kind == "location-switched":
            for location in (message.get("location", {}), message.get("previous", {}).get("location", {})):
                if not scoped_directory(location.get("directory"), root):
                    raise ValueError("OpenCode history includes another project")
        elif kind in {"user", "synthetic", "system", "skill"}:
            if not isinstance(message.get("text"), str):
                raise ValueError("invalid OpenCode 2 message text")
            entries.append({"type": "message" if kind == "user" else "intermediate",
                            "role": "user" if kind in {"user", "synthetic"} else "system",
                            "content": message["text"]})
            if kind == "user":
                files = message.get("files", [])
                if not isinstance(files, list) or not all(isinstance(item, dict) for item in files):
                    raise ValueError("invalid OpenCode 2 attachments")
                if files:
                    entries.append({"type": "message", "role": "user", "content": [attachment(item) for item in files]})
        elif kind == "assistant":
            content = message.get("content")
            if not isinstance(content, list):
                raise ValueError("invalid OpenCode 2 assistant content")
            final = (message.get("time", {}).get("completed") is not None
                     and message.get("finish") in {"stop", "length", "content-filter"}
                     and not message.get("error"))
            for part in content:
                if not isinstance(part, dict):
                    raise ValueError("invalid OpenCode 2 content part")
                if part.get("type") in {"text", "reasoning"}:
                    if not isinstance(part.get("text"), str):
                        raise ValueError("invalid OpenCode 2 content text")
                    event_type = "reasoning" if part["type"] == "reasoning" else "message" if final else "intermediate"
                    entries.append({"type": event_type, "role": "assistant", "content": part["text"]})
                elif part.get("type") == "tool":
                    state = part.get("state", {})
                    if (not isinstance(part.get("id"), str) or not isinstance(part.get("name"), str)
                            or not isinstance(state, dict) or state.get("status") not in {"streaming", "running", "completed", "error"}
                            or not isinstance(state.get("input"), (dict, str))):
                        raise ValueError("invalid OpenCode 2 tool")
                    entries.append({"type": "tool_call", "name": part["name"], "call_id": part["id"], "input": state["input"]})
                    if state["status"] in {"completed", "error"}:
                        content = state.get("content", [])
                        if not isinstance(content, list) or not all(isinstance(item, dict) for item in content):
                            raise ValueError("invalid OpenCode 2 tool result")
                        result = [attachment(item) if item.get("type") == "file"
                                  else {"type": "text", "text": item["text"]}
                                  for item in content if item.get("type") == "file" or isinstance(item.get("text"), str)]
                        if state["status"] == "error":
                            error = state.get("error", {})
                            result.append({"type": "text", "text": error.get("message", "工具执行失败")})
                        entries.append({"type": "tool_result", "call_id": part["id"],
                                        "content": result, "is_error": state["status"] == "error"})
        elif kind == "compaction" and isinstance(message.get("summary"), str):
            entries.append({"type": "intermediate", "role": "system", "content": message["summary"]})
        for index, entry in enumerate(entries):
            yield {**entry, "message_id": mid, "part": index, "timestamp": stamp}


def merge_v2(records, previous, messages, mode):
    """The 2.x context API drops pre-compaction messages; retain archived history."""
    replaced = {message["id"] for message in messages}
    for row in previous:
        if (not isinstance(row, dict) or not isinstance(row.get("message_id"), str)
                or not isinstance(row.get("timestamp"), str) or not isinstance(row.get("part"), int)):
            raise ValueError("invalid OpenCode 2 archive entry")
    combined = [row for row in previous if row["message_id"] not in replaced] + records
    combined.sort(key=lambda row: (row["timestamp"], row["message_id"], row["part"]))
    turns = {}
    result = []
    for row in combined:
        if row["type"] == "message" and row.get("role") == "user":
            turns.setdefault(row["message_id"], len(turns) + 1)
        if (row["type"] == "message" or mode == "full"
                or (row["type"] == "tool_call" and mode == "tool-calls")):
            result.append({**row, "turn": len(turns) or 1})
    return result


def handle(payload, project_root):
    root = Path(project_root).resolve()
    if not isinstance(payload, dict) or not scoped_directory(payload.get("directory"), root):
        return
    config = read_archive_config(root, "opencode")
    if config is None:
        return
    session = payload.get("session")
    version = payload.get("version", 1)
    if version not in {1, 2} or not isinstance(session, dict):
        return
    session_directory = session.get("location", {}).get("directory") if version == 2 else session.get("directory")
    if not scoped_directory(session_directory, root):
        return
    sid = archive_session_id(session.get("id"))
    messages = payload.get("messages")
    if sid is None or not isinstance(messages, list):
        raise ValueError("invalid OpenCode session snapshot")
    started = timestamp(session.get("time", {}).get("created"))
    source = v2_events(messages, root) if version == 2 else events(messages, session["id"], config["mode"], root)
    records = [sanitize_content(event) for event in source]
    if not records and version == 1:
        return
    directory = prepare_archive_directory(root, "opencode")
    path = session_archive_path(directory, sid, started)
    if path.is_symlink():
        raise ValueError("refusing a symlink archive")
    previous = []
    if path.exists():
        with path.open(encoding="utf-8") as source:
            header = json.loads(source.readline())
            if version == 2:
                previous = [json.loads(line) for line in source if line.strip()]
        if (not isinstance(header, dict) or header.get("type") != "session"
                or header.get("schema_version") != 1 or header.get("agent") != "opencode"
                or header.get("session_id") != session["id"]):
            raise ValueError("existing archive belongs to a different session")
        started = header["started_at"]
    if version == 2:
        records = merge_v2(records, previous, messages, config["mode"])
    if not records:
        return
    header = session_header("opencode", session["id"], config["mode"], started)
    atomic_write(path, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in [header, *records]))


def install_hooks(root):
    root = Path(root).resolve()
    config = root / ".opencode"
    paths = [config, config / "plugins", config / "ucore-hooks"]
    sources = Path(__file__).resolve().parent
    files = [(sources / name, config / "ucore-hooks" / name)
             for name in ("archive_session.py", "archive_storage.py", "opencode_hook.py")]
    files.append((sources / "opencode_plugin.js", config / "plugins/ucore-session-archive.js"))
    if any(path.is_symlink() for path in [*paths, *(destination for _, destination in files)]):
        raise ValueError("OpenCode project configuration must not be a symlink")
    for path in paths[:2]:
        path.mkdir(mode=0o700, exist_ok=True)
    private_directory(config / "ucore-hooks")
    for source, destination in files:
        atomic_write(destination, source.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    try:
        handle(json.load(sys.stdin), args.project)
    except Exception as error:
        print(f"ucore-session-archive: OpenCode 归档未完成（{type(error).__name__}）；请检查项目配置及归档目录权限。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
