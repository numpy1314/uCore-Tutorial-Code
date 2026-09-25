// Drive the installed plugin with the public SDK shape and the real Python adapter.
import assert from "node:assert/strict";
import { readFile, writeFile, mkdir, unlink } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const root = process.argv[2];
let input = "";
for await (const chunk of process.stdin) input += chunk;
const payload = JSON.parse(input);
const { default: definition } = await import(pathToFileURL(join(root, ".opencode/plugins/ucore-session-archive.js")));
assert.equal(definition.id, "ucore-session-archive");
assert.equal(typeof definition.setup, "function");
const CourseSessionArchive = definition.server;
let reads = 0;
let logs = 0;
let fail = false;
let sessionDirectory = root;
const client = {
  app: { log: async () => { logs++; } },
  session: {
    get: async (options) => {
      assert.deepEqual(options, { path: { id: payload.session.id }, query: { directory: root } });
      return { data: { ...payload.session, directory: sessionDirectory } };
    },
    messages: async (options) => {
      assert.equal(options.path.id, payload.session.id);
      reads++;
      return fail ? { error: { message: "SOURCE_ERROR" } } : { data: payload.messages };
    },
  },
};
const plugin = await CourseSessionArchive({ client, directory: root });
const event = { event: { type: "session.idle", properties: { sessionID: payload.session.id } } };
await plugin.event({ event: { type: "message.updated", properties: {} } });
assert.equal(reads, 0);
const policy = join(root, ".opencode/session-archive.json");
const original = await readFile(policy, "utf8");
for (const value of ['{"enabled":false}', 'null', '{"enabled":']) {
  await writeFile(policy, value);
  await plugin.event(event);
  assert.equal(reads, 0);
}
await unlink(policy);
await plugin.event(event);
assert.equal(reads, 0);
assert.equal(logs, 0);
await writeFile(policy, original);
sessionDirectory = "/";
await plugin.event(event);
assert.equal(reads, 0);
sessionDirectory = join(root, "nested");
await mkdir(join(sessionDirectory, ".opencode"), { recursive: true });
await writeFile(join(sessionDirectory, ".opencode/session-archive.json"), '{"enabled":false}');
await plugin.event(event);
assert.equal(reads, 0);
sessionDirectory = root;
const outside = await CourseSessionArchive({ client, directory: "/" });
await outside.event(event);
assert.equal(reads, 0);
fail = true;
await plugin.event(event);
assert.equal(logs, 1);
fail = false;
await Promise.all([plugin.event(event), plugin.event(event)]);
assert.equal(reads, 3);
assert.equal(logs, 1);
