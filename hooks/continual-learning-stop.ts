/**
 * Wrapper for Continual Learning plugin stop hook.
 * Cursor runs hooks with cwd = workspace, so it looks for ./hooks/continual-learning-stop.ts
 * here. This script finds the plugin's real script and runs it (keeping cwd = workspace
 * so plugin state lives in this repo's .cursor/hooks/state).
 */
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const PLUGIN_BASE = join(
  homedir(),
  ".cursor",
  "plugins",
  "cache",
  "cursor-public",
  "continual-learning"
);

function findPluginScript(): string | null {
  if (!existsSync(PLUGIN_BASE)) return null;
  const entries = readdirSync(PLUGIN_BASE, { withFileTypes: true });
  for (const e of entries) {
    if (!e.isDirectory()) continue;
    const script = join(PLUGIN_BASE, e.name, "hooks", "continual-learning-stop.ts");
    if (existsSync(script)) return script;
  }
  return null;
}

const script = findPluginScript();
if (!script) {
  console.error("[continual-learning-stop] Plugin script not found under", PLUGIN_BASE);
  console.log(JSON.stringify({}));
  process.exit(0);
}

const proc = Bun.spawn({
  cmd: ["bun", "run", script, ...process.argv.slice(2)],
  stdin: "inherit",
  stdout: "inherit",
  stderr: "inherit",
  cwd: process.cwd(),
});
const code = await proc.exited;
process.exit(code);
