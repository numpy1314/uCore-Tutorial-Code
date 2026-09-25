import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import opencode_hook as hook


def snapshot(root, sid="ses_example"):
    messages = []

    def message(mid, role, parts, **extra):
        info = {"id": mid, "sessionID": sid, "role": role,
                "time": {"created": 1789129800000 + len(messages) * 1000}, **extra}
        if role == "assistant":
            info.update(path={"cwd": str(root), "root": str(root)}, parentID="msg_user")
            info["time"]["completed"] = info["time"]["created"] + 500
        messages.append({"info": info, "parts": [
            {"id": f"{mid}_{i}", "sessionID": sid, "messageID": mid, **part}
            for i, part in enumerate(parts)]})

    message("msg_user", "user", [{"type": "text", "text": "QUESTION\n第二行"}])
    message("msg_tool", "assistant", [
        {"type": "text", "text": "COMMENTARY"},
        {"type": "reasoning", "text": "REASONING", "metadata": {"signature": "OPAQUE"}},
        {"type": "tool", "tool": "bash", "callID": "call_one", "state": {
            "status": "completed", "input": {"command": "git status", "signature": "OPAQUE"},
            "output": "TOOL_OUTPUT", "attachments": [{"url": "data:image/png;base64,BINARY"}]}}
    ], finish="tool-calls")
    message("msg_final", "assistant", [{"type": "text", "text": "ANSWER"}], finish="stop")
    return {"directory": str(root), "session": {"id": sid, "directory": str(root),
            "time": {"created": 1789129800000, "updated": 1789129803000}}, "messages": messages}


class OpenCodeArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "project with spaces"
        self.root.mkdir()
        self.policy = self.root / ".opencode/session-archive.json"
        self.policy.parent.mkdir()
        self.configure()
        self.payload = snapshot(self.root)

    def configure(self, mode="messages", enabled=True):
        self.policy.write_text(json.dumps({"enabled": enabled, "mode": mode}))

    def archive(self, payload=None):
        hook.handle(payload or self.payload, self.root)

    def files(self):
        return list((self.root / ".ai/agent-sessions/opencode").glob("*.jsonl"))

    def records(self):
        return [json.loads(line) for line in self.files()[0].read_text().splitlines()]

    def test_modes_filter_content_and_refresh_one_stable_file(self):
        for mode, kinds in (("messages", ["message", "message"]),
                            ("tool-calls", ["message", "tool_call", "message"]),
                            ("full", ["message", "intermediate", "reasoning", "tool_call", "tool_result", "message"]),
                            ("messages", ["message", "message"])):
            with self.subTest(mode=mode):
                self.configure(mode)
                self.archive()
                self.archive()
                self.assertEqual(1, len(self.files()))
                path = self.files()[0]
                self.assertEqual("2026-09-11_12-30-00_ses_example.jsonl", path.name)
                records = self.records()
                self.assertEqual(mode, records[0]["mode"])
                self.assertEqual(kinds, [row["type"] for row in records[1:]])
                self.assertEqual({1}, {row["turn"] for row in records[1:]})
                self.assertEqual("QUESTION\n第二行", records[1]["content"])
                self.assertNotIn("OPAQUE", path.read_text())
                self.assertNotIn("BINARY", path.read_text())
                self.assertEqual(0o600, path.stat().st_mode & 0o777)
                if mode != "full":
                    for text in ("TOOL_OUTPUT", "COMMENTARY", "REASONING"):
                        self.assertNotIn(text, path.read_text())

    def test_repeated_text_in_different_turns_and_separate_sessions(self):
        extra = copy.deepcopy(self.payload["messages"])
        for item in extra:
            item["info"]["id"] += "_next"
            if "parentID" in item["info"]:
                item["info"]["parentID"] += "_next"
            for part in item["parts"]:
                part["id"] += "_next"
                part["messageID"] += "_next"
        self.payload["messages"].extend(extra)
        self.archive()
        self.assertEqual([1, 1, 2, 2], [row["turn"] for row in self.records()[1:]])
        self.archive(snapshot(self.root, "another_session"))
        self.assertEqual(2, len(self.files()))

    def test_project_scope_disabled_policy_and_nested_policy(self):
        outside = self.root.parent / "other"
        outside.mkdir()
        for field in ("directory", "session"):
            payload = copy.deepcopy(self.payload)
            if field == "directory":
                payload[field] = str(outside)
            else:
                payload[field]["directory"] = str(outside)
            self.archive(payload)
            self.assertFalse(self.files())
        self.configure(enabled=False)
        self.archive()
        self.assertFalse(self.files())
        self.configure()
        child = self.root / "chapter"
        child.mkdir()
        self.payload["directory"] = str(child)
        child_policy = child / ".opencode/session-archive.json"
        child_policy.parent.mkdir()
        child_policy.write_text('{"enabled": false}')
        self.archive()
        self.assertFalse(self.files())
        self.payload["directory"] = str(self.root)
        self.payload["session"]["directory"] = str(child)
        self.archive()
        self.assertFalse(self.files())
        child_policy.unlink()
        self.archive()
        self.assertEqual(1, len(self.files()))

    def test_missing_malformed_and_symlink_policies_do_not_record(self):
        for contents in ("{", "null", '{"enabled": "true"}'):
            self.policy.write_text(contents)
            self.archive()
            self.assertFalse(self.files())
        self.policy.unlink()
        self.archive()
        self.assertFalse(self.files())
        outside = self.root.parent / "external.json"
        outside.write_text('{"enabled": true}')
        self.policy.symlink_to(outside)
        self.archive()
        self.assertFalse(self.files())

    def test_invalid_or_foreign_snapshot_preserves_last_archive(self):
        self.archive()
        before = self.files()[0].read_bytes()
        for kind in ("missing_parts", "foreign_message", "foreign_part", "outside_cwd", "empty"):
            payload = copy.deepcopy(self.payload)
            if kind == "missing_parts":
                del payload["messages"][-1]["parts"]
            elif kind == "foreign_message":
                payload["messages"][-1]["info"]["sessionID"] = "someone_else"
            elif kind == "foreign_part":
                payload["messages"][-1]["parts"][0]["messageID"] = "someone_else"
            elif kind == "outside_cwd":
                payload["messages"][-1]["info"]["path"]["cwd"] = str(self.root.parent)
            else:
                payload["messages"] = []
            with self.subTest(kind=kind):
                if kind != "empty":
                    with self.assertRaises(ValueError):
                        self.archive(payload)
                else:
                    self.archive(payload)
                self.assertEqual(before, self.files()[0].read_bytes())

    def test_attachments_synthetic_messages_and_tool_errors(self):
        user = self.payload["messages"][0]
        user["parts"].extend([
            {**user["parts"][0], "id": "image", "type": "file", "mime": "image/png",
             "filename": "diagram.png", "url": "data:image/png;base64,BINARY"},
            {**user["parts"][0], "id": "synthetic", "synthetic": True, "text": "SYNTHETIC"},
        ])
        state = self.payload["messages"][1]["parts"][-1]["state"]
        state.update(status="error", error="FAILED_TOOL")
        self.archive()
        self.assertNotIn("SYNTHETIC", self.files()[0].read_text())
        self.assertIn("diagram.png", self.files()[0].read_text())
        self.configure("full")
        self.archive()
        text = self.files()[0].read_text()
        self.assertNotIn("BINARY", text)
        self.assertIn("SYNTHETIC", text)
        result = next(row for row in self.records() if row["type"] == "tool_result")
        self.assertTrue(result["is_error"])
        self.assertEqual("FAILED_TOOL", result["content"])

    def test_symlink_archive_directory_is_rejected(self):
        outside = self.root.parent / "external"
        outside.mkdir()
        (self.root / ".ai").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.archive()
        self.assertFalse(list(outside.iterdir()))

    def test_installer_preserves_existing_plugins_and_settings(self):
        settings = self.policy.parent / "opencode.json"
        settings.write_text('{"plugin": ["other-plugin"]}')
        plugins = self.policy.parent / "plugins"
        plugins.mkdir()
        self.policy.parent.chmod(0o755)
        plugins.chmod(0o755)
        other = plugins / "other.js"
        other.write_text("export const other = async () => ({});")
        for _ in range(2):
            hook.install_hooks(self.root)
        self.assertEqual('{"plugin": ["other-plugin"]}', settings.read_text())
        self.assertEqual("export const other = async () => ({});", other.read_text())
        self.assertEqual(2, len(list(plugins.iterdir())))
        self.assertEqual(0o755, self.policy.parent.stat().st_mode & 0o777)
        self.assertEqual(0o755, plugins.stat().st_mode & 0o777)
        runtime = self.policy.parent / "ucore-hooks/opencode_hook.py"
        self.assertTrue(runtime.is_file())
        runtime.unlink()
        runtime.symlink_to(settings)
        with self.assertRaises(ValueError):
            hook.install_hooks(self.root)
        self.assertEqual('{"plugin": ["other-plugin"]}', settings.read_text())

    def test_real_js_bridge_sdk_contract_scope_and_recovery(self):
        node = shutil.which("node") or next((str(path) for path in
            (Path.home() / ".vscode-server/bin").glob("*/node") if path.is_file()), None)
        if not node:
            self.skipTest("Node.js is required to exercise the OpenCode plugin")
        hook.install_hooks(self.root)
        driver = Path(__file__).with_name("opencode_bridge.mjs")
        result = subprocess.run([node, str(driver), str(self.root)], input=json.dumps(self.payload),
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("ANSWER", self.records()[-1]["content"])
        self.assertEqual(1, len(self.files()))


if __name__ == "__main__":
    unittest.main()
