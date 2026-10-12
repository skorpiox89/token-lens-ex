import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

/**
 * yuque-mcp
 *
 * 把包内 mcp/yuque/ 的本地 stdio 服务注册为 pi 的 MCP server（配置即代码）：
 * 装了 token-lens-ex 包就自动生效，不需要在 mcp.json 里维护条目。
 *
 * 环境解析顺序（详见 skills/yuque-mcp/SKILL.md）：
 *   cookie:  YUQUE_COOKIE 环境变量 → 数据目录 cookie.txt → ~/yuque-mcp/cookie.txt
 *   token:   YUQUE_TOKEN 环境变量（官方 OpenAPI，优先于 cookie）
 *   运行:    数据目录 venv → 系统 uv（uv run --with 'mcp>=1.2.0,<2'）
 *
 * 秘密只留在机器上，不写入仓库；mcp.json 里同名条目会覆盖扩展注册，
 * 因此使用本扩展时应避免在 mcp.json 里再写一份 yuque。
 */

const SERVER_NAME = "yuque";
const MCP_SPEC = "mcp>=1.2.0,<2";

const extensionDir = dirname(fileURLToPath(import.meta.url));
const packageRoot = join(extensionDir, "..", "..", "..");
const serverPy = join(packageRoot, "mcp", "yuque", "server.py");

const dataDir = join(
  process.env.XDG_DATA_HOME?.trim() || join(homedir(), ".local", "share"),
  "token-lens-ex",
  "mcp",
  "yuque"
);
const venvPython =
  process.platform === "win32"
    ? join(dataDir, "venv", "Scripts", "python.exe")
    : join(dataDir, "venv", "bin", "python");

const cookieFiles = [join(dataDir, "cookie.txt"), join(homedir(), "yuque-mcp", "cookie.txt")];

function readFirstFile(paths: string[]): string | undefined {
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

function hasExecutable(name: string): boolean {
  const pathValue = process.env.PATH ?? "";
  const separator = process.platform === "win32" ? ";" : ":";
  const executable = process.platform === "win32" ? name.replace(/\.exe$/i, "") : name;
  const extensions =
    process.platform === "win32" ? (process.env.PATHEXT ?? ".EXE;.CMD;.BAT").split(";").filter(Boolean) : [""];
  return pathValue.split(separator).some((dir) =>
    dir ? extensions.some((ext) => existsSync(join(dir, `${executable}${ext}`))) : false
  );
}

export default (pi: ExtensionAPI) => {
  const warn = (message: string) => {
    pi.on("session_start", (_event, ctx) => {
      ctx.ui.notify(message, "warning");
    });
  };

  if (!existsSync(serverPy)) {
    warn(`yuque MCP：包内缺少 ${serverPy}，请更新 token-lens-ex 包。`);
    return;
  }

  const token = process.env.YUQUE_TOKEN?.trim();
  const cookie = process.env.YUQUE_COOKIE?.trim() || readFirstFile(cookieFiles);
  if (!token && !cookie) {
    warn(
      `yuque MCP 未注册：未找到 YUQUE_TOKEN / YUQUE_COOKIE。按 skills/yuque-mcp/SKILL.md 配置（cookie 可放 ${cookieFiles[0]}），然后重开会话。`
    );
    return;
  }

  const env: Record<string, string> = { YUQUE_LOGIN: process.env.YUQUE_LOGIN?.trim() || "huangxuantao" };
  if (token) env.YUQUE_TOKEN = token;
  if (cookie) env.YUQUE_COOKIE = cookie;

  let command: string;
  let args: string[];
  if (existsSync(venvPython)) {
    command = venvPython;
    args = [serverPy];
  } else if (hasExecutable(process.platform === "win32" ? "uv.exe" : "uv")) {
    command = process.platform === "win32" ? "uv.exe" : "uv";
    args = ["run", "--quiet", "--with", MCP_SPEC, serverPy];
  } else {
    warn(
      `yuque MCP 未注册：缺少 Python 环境。请运行包内 mcp/yuque/setup.sh 建 venv，或安装 uv 后重开会话。`
    );
    return;
  }

  pi.registerMcpServer(SERVER_NAME, {
    command,
    args,
    env,
    exposure: "deferred",
    description: "语雀知识库（本地 Cookie 模式，无需会员；文档/知识库读写）",
  });
};
