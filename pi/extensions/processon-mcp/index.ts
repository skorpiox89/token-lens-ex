import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { mcpDataDir, packageRoot, pythonRuntime, readFirstFile, warnOnStart } from "../lib/mcp-support.ts";

/**
 * processon-mcp：注册包内 mcp/processon/server.py 为 pi 的 MCP server（配置即代码）。
 * cookie：PROCESSON_COOKIE 环境变量 → 数据目录 cookie.txt → ~/processon-mcp/cookie.txt。
 * 也支持 PROCESSON_ACCOUNT / PROCESSON_PASSWORD（账号密码模式），有则一并传入。
 */

const NAME = "processon";
const SERVER_NAME = "processon";
const dataDir = mcpDataDir(NAME);
const serverPy = join(packageRoot(import.meta.url), "mcp", NAME, "server.py");

export default (pi: ExtensionAPI) => {
  if (!existsSync(serverPy)) {
    warnOnStart(pi, `${SERVER_NAME} MCP：包内缺少 ${serverPy}，请更新 token-lens-ex 包。`);
    return;
  }

  const cookie =
    process.env.PROCESSON_COOKIE?.trim() ||
    readFirstFile([join(dataDir, "cookie.txt"), join(homedir(), "processon-mcp", "cookie.txt")]);
  const account = process.env.PROCESSON_ACCOUNT?.trim();
  const password = process.env.PROCESSON_PASSWORD?.trim();
  if (!cookie && !(account && password)) {
    warnOnStart(
      pi,
      `${SERVER_NAME} MCP 未注册：未找到 PROCESSON_COOKIE（或账号密码）。按 skills/${SERVER_NAME}-mcp/SKILL.md 配置（cookie 可放 ${join(dataDir, "cookie.txt")}），然后重开会话。`
    );
    return;
  }

  const runtime = pythonRuntime(dataDir, serverPy);
  if (!runtime) {
    warnOnStart(pi, `${SERVER_NAME} MCP 未注册：缺少 Python 环境。请运行 mcp/setup.sh ${NAME}，或安装 uv 后重开会话。`);
    return;
  }

  const env: Record<string, string> = {};
  if (cookie) env.PROCESSON_COOKIE = cookie;
  if (account) env.PROCESSON_ACCOUNT = account;
  if (password) env.PROCESSON_PASSWORD = password;

  pi.registerMcpServer(SERVER_NAME, {
    command: runtime.command,
    args: runtime.args,
    env,
    exposure: "deferred",
    description: "ProcessOn（只读：目录树/图表定义/Mermaid 转换/批量导出）",
  });
};
