import copy
import json
import tempfile
import unittest
from pathlib import Path

from test_opencode_hook import hook


def snapshot_v2(root):
    base = {"agent": "build", "model": {"providerID": "course-test-missing", "id": "course-test-missing"}}
    return {"version": 2, "directory": str(root), "session": {
        "id": "ses_v2_example", "location": {"directory": str(root)}, "time": {"created": 1789129800000}},
        "messages": [
            {"id": "msg_001", "type": "user", "text": "V2_QUESTION", "time": {"created": 1789129800000},
             "files": [{"mime": "image/png", "name": "diagram.png", "data": "QklOQVJZ", "source": {"type": "inline"}}]},
            {"id": "msg_002", "type": "assistant", **base, "time": {"created": 1789129801000, "completed": 1789129801500},
             "finish": "tool-calls", "content": [
                 {"type": "text", "text": "V2_COMMENTARY"},
                 {"type": "reasoning", "text": "V2_REASONING", "state": {"opaque": "PROVIDER_SECRET"}},
                 {"type": "tool", "id": "call_v2", "name": "bash", "time": {"created": 1789129801000},
                  "state": {"status": "completed", "input": {"command": "git status"}, "content": [
                      {"type": "text", "text": "V2_TOOL_OUTPUT"},
                      {"type": "file", "mime": "image/png", "name": "result.png", "uri": "data:image/png;base64,QklOQVJZ"}]}}
             ]},
            {"id": "msg_003", "type": "assistant", **base, "time": {"created": 1789129802000, "completed": 1789129802500},
             "finish": "stop", "content": [{"type": "text", "text": "V2_ANSWER"}], "providerState": {"opaque": "PROVIDER_SECRET"}},
        ]}


class OpenCodeV2Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.policy = self.root / ".opencode/session-archive.json"
        self.policy.parent.mkdir()
        self.configure("full")
        self.payload = snapshot_v2(self.root)

    def configure(self, mode):
        self.policy.write_text(json.dumps({"enabled": True, "mode": mode}))

    def records(self):
        files = list((self.root / ".ai/agent-sessions/opencode").glob("*.jsonl"))
        self.assertEqual(1, len(files))
        return [json.loads(line) for line in files[0].read_text().splitlines()]

    def test_all_modes_and_repeated_callbacks(self):
        for mode in ("messages", "tool-calls", "full", "messages"):
            self.configure(mode)
            hook.handle(self.payload, self.root)
            before = self.records()
            hook.handle(self.payload, self.root)
            self.assertEqual(before, self.records())
            text = json.dumps(before)
            self.assertIn("V2_QUESTION", text)
            self.assertIn("V2_ANSWER", text)
            self.assertIn("diagram.png", text)
            self.assertNotIn("PROVIDER_SECRET", text)
            self.assertNotIn("QklOQVJZ", text)
            self.assertEqual(mode != "messages", any(row["type"] == "tool_call" for row in before))
            self.assertEqual(mode == "full", "V2_REASONING" in text)
            self.assertEqual(mode == "full", "V2_TOOL_OUTPUT" in text)

    def test_compaction_keeps_archived_history_and_applies_mode_downgrade(self):
        hook.handle(self.payload, self.root)
        self.payload["messages"] = [{"id": "msg_004", "type": "compaction", "status": "completed", "summary": "SUMMARY",
                                     "time": {"created": 1789129803000}},
                                    {"id": "msg_005", "type": "user", "text": "NEXT_QUESTION", "time": {"created": 1789129804000}}]
        hook.handle(self.payload, self.root)
        records = self.records()
        self.assertIn("V2_ANSWER", json.dumps(records))
        self.assertIn("V2_TOOL_OUTPUT", json.dumps(records))
        self.assertEqual(2, records[-1]["turn"])
        self.configure("messages")
        hook.handle(self.payload, self.root)
        text = json.dumps(self.records())
        self.assertIn("V2_ANSWER", text)
        self.assertNotIn("V2_TOOL_OUTPUT", text)
        self.assertNotIn("SUMMARY", text)

    def test_foreign_or_moved_session_does_not_write(self):
        self.payload["session"]["location"]["directory"] = str(self.root.parent)
        hook.handle(self.payload, self.root)
        self.assertFalse((self.root / ".ai").exists())
        self.payload["session"]["location"]["directory"] = str(self.root)
        self.payload["messages"].insert(0, {"id": "msg_move", "type": "location-switched", "time": {"created": 1789129800000},
            "location": {"directory": str(self.root)}, "previous": {"location": {"directory": str(self.root.parent)}}})
        with self.assertRaises(ValueError):
            hook.handle(self.payload, self.root)
        self.assertFalse((self.root / ".ai").exists())

    def test_invalid_context_preserves_archive(self):
        hook.handle(self.payload, self.root)
        before = self.records()
        for kind in ("duplicate", "invalid_content"):
            payload = copy.deepcopy(self.payload)
            if kind == "duplicate":
                payload["messages"].append(payload["messages"][0])
            else:
                payload["messages"][-1]["content"] = None
            with self.assertRaises(ValueError):
                hook.handle(payload, self.root)
            self.assertEqual(before, self.records())
