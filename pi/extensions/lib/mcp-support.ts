import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

/**
 * token-lens-ex MCP 扩展的共享工具：定位包目录与数据目录、读取本地秘密、
 * 解析 Python 运行环境（venv 优先、uv 回退）、启动时提示。
 *
 * 约定：代码随 pi 包分发（mcp/<name>/），环境与秘密只留机器本地
 * （数据目录 ~/.local/share/token-lens-ex/mcp/<name>/）。
 */

export function packageRoot(extensionUrl: string): string {
  return join(dirname(fileURLToPath(extensionUrl)), "..", "..", "..");
}

export function mcpDataDir(name: string): string {
  const base = process.env.XDG_DATA_HOME?.trim() || join(homedir(), ".local", "share");
  return join(base, "token-lens-ex", "mcp", name);
}

export function readFirstFile(paths: string[]): string | undefined {
  for (const path of paths) {
    try {
      const value = readFileSync(path, "utf8").trim();
      if (value) return value;
    } catch {
      // 尝试下一个
    }
  }
  return undefined;
}

export function hasExecutable(name: string): boolean {
  const pathValue = process.env.PATH ?? "";
  const separator = process.platform === "win32" ? ";" : ":";
  const executable = process.platform === "win32" ? name.replace(/\.(exe|cmd|bat)$/i, "") : name;
  const extensions =
    process.platform === "win32" ? (process.env.PATHEXT ?? ".EXE;.CMD;.BAT").split(";").filter(Boolean) : [""];
  return pathValue
    .split(separator)
    .some((dir) => (dir ? extensions.some((ext) => existsSync(join(dir, `${executable}${ext}`))) : false));
}

/** Python 运行环境：数据目录 venv 优先；否则有 uv 时用 `uv run --with` 动态装依赖。 */
export function pythonRuntime(
  dataDir: string,
  scriptPath: string,
  mcpSpec = "mcp>=1.2.0,<2"
): { command: string; args: string[] } | null {
  const venvPython =
    process.platform === "win32"
      ? join(dataDir, "venv", "Scripts", "python.exe")
      : join(dataDir, "venv", "bin", "python");
  if (existsSync(venvPython)) {
    return { command: venvPython, args: [scriptPath] };
  }
  const uv = process.platform === "win32" ? "uv.exe" : "uv";
  if (hasExecutable(uv)) {
    return { command: uv, args: ["run", "--quiet", "--with", mcpSpec, scriptPath] };
  }
  return null;
}

/** 在会话启动时以 warning 提示（不打断启动）。 */
export function warnOnStart(pi: ExtensionAPI, message: string): void {
  pi.on("session_start", (_event, ctx) => {
    ctx.ui.notify(message, "warning");
  });
}
