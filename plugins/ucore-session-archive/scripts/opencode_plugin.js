// Project-local OpenCode plugin. Uses only built-ins and the provided SDK client.
import { spawn } from "node:child_process";
import { lstat, readFile, realpath } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(dirname(fileURLToPath(import.meta.url))));

async function scoped(directory) {
  if (typeof directory !== "string" || !isAbsolute(directory)) return false;
  const current = await realpath(directory);
  const path = relative(root, current);
  if (path === ".." || path.startsWith(`..${sep}`) || isAbsolute(path)) return false;
  // A nearer policy, including a disabled one, belongs to a separate project.
  for (let candidate = current; candidate !== root; candidate = dirname(candidate)) {
    try {
      await lstat(join(candidate, ".opencode/session-archive.json"));
      return false;
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
  return true;
}

async function enabled(directory) {
  if (!await scoped(directory)) return false;
  try {
    for (const path of [join(root, ".opencode"), join(root, ".opencode/session-archive.json")]) {
      if ((await lstat(path)).isSymbolicLink()) return false;
    }
    const config = JSON.parse(await readFile(join(root, ".opencode/session-archive.json"), "utf8"));
    return config?.enabled === true;
  } catch (error) {
    if (error.code === "ENOENT" || error instanceof SyntaxError) return false;
    throw error;
  }
}

function archive(payload) {
  return new Promise((resolve, reject) => {
    const child = spawn("python3", [join(root, ".opencode/ucore-hooks/opencode_hook.py"), "--project", root], {
      cwd: root, stdio: ["pipe", "ignore", "ignore"],
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
    });
    const timeout = setTimeout(() => child.kill(), 30000);
    child.on("error", (error) => { clearTimeout(timeout); reject(error); });
    child.on("close", (code) => {
      clearTimeout(timeout);
      if (code === 0) resolve();
      else reject(new Error("archive process failed"));
    });
    child.stdin.on("error", reject);
    child.stdin.end(JSON.stringify(payload));
  });
}

const CourseSessionArchive = async ({ client, directory }) => {
  const pending = new Map();
  async function report() {
    try {
      await client.app.log({ body: { service: "ucore-session-archive", level: "warn",
        message: "OpenCode 会话归档未完成；请检查 Python 3、项目配置及归档目录权限。" } });
    } catch { /* Recording must never interrupt the agent. */ }
  }
  async function capture(id) {
    if (!await enabled(directory)) return;
    const options = { path: { id }, query: { directory } };
    const session = await client.session.get(options);
    if (session.error || !session.data || session.data.id !== id) throw new Error("session unavailable");
    // Check the session before asking the SDK for any conversation content.
    if (!await scoped(session.data.directory)) return;
    const messages = await client.session.messages(options);
    if (messages.error || !Array.isArray(messages.data)) throw new Error("messages unavailable");
    if (!await enabled(directory)) return;
    await archive({ directory, session: session.data, messages: messages.data });
  }
  return {
    event: async ({ event }) => {
      if (event.type !== "session.idle" && event.type !== "session.error") return;
      const id = event.properties?.sessionID;
      if (typeof id !== "string" || !id) return;
      // Serialize reads and writes for each session so repeated idle events cannot race.
      const job = (pending.get(id) ?? Promise.resolve()).then(() => capture(id)).catch(report);
      pending.set(id, job);
      await job;
      if (pending.get(id) === job) pending.delete(id);
    },
  };
};

// OpenCode 2 uses a default definition, an async event stream, and native session APIs.
// `server` also lets the v1 module loader use its original hooks/SDK adapter.
export default {
  id: "ucore-session-archive",
  server: CourseSessionArchive,
  setup: async (context) => {
    const directory = context.location.directory;
    const controller = new AbortController();
    const completed = new Set([
      "session.execution.succeeded", "session.execution.failed", "session.execution.interrupted",
      "session.compaction.ended",
    ]);
    const report = () => console.warn("ucore-session-archive: OpenCode 归档未完成；请检查 Python 3、项目配置及归档目录权限。");
    const capture = async (event) => {
      if (!completed.has(event.type) || !await enabled(directory)) return;
      // Execution events may omit location; get() supplies the authoritative scope.
      if (event.location && !await scoped(event.location.directory)) return;
      const id = event.data?.sessionID;
      if (typeof id !== "string" || !id) return;
      const session = await context.session.get({ sessionID: id });
      if (!session || session.id !== id) throw new Error("session unavailable");
      if (!await scoped(session.location?.directory)) return;
      const messages = await context.session.context({ sessionID: id });
      if (!Array.isArray(messages)) throw new Error("messages unavailable");
      if (!await enabled(directory)) return;
      await archive({ version: 2, directory, session, messages });
    };
    // Keep setup finite; the host owns this subscription until cleanup/reload.
    const task = (async () => {
      try {
        for await (const event of context.event.subscribe({ signal: controller.signal })) {
          if (controller.signal.aborted) break;
          try { await capture(event); } catch { report(); }
        }
      } catch {
        if (!controller.signal.aborted) report();
      }
    })();
    return async () => { controller.abort(); await task; };
  },
};
