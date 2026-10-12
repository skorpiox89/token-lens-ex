import { existsSync } from "node:fs";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { mcpDataDir, packageRoot, pythonRuntime, readFirstFile, warnOnStart } from "../lib/mcp-support.ts";

/**
 * weibo-mcp：注册包内 mcp/weibo/server.py 为 pi 的 MCP server（配置即代码）。
 * cookie：WEIBO_COOKIE 环境变量 → 数据目录 cookie.txt → ~/weibo-mcp/cookie.txt。
 */

const NAME = "weibo";
const SERVER_NAME = "weibo";
const dataDir = mcpDataDir(NAME);
const serverPy = join(packageRoot(import.meta.url), "mcp", NAME, "server.py");

export default (pi: ExtensionAPI) => {
  if (!existsSync(serverPy)) {
    warnOnStart(pi, `${SERVER_NAME} MCP：包内缺少 ${serverPy}，请更新 token-lens-ex 包。`);
    return;
  }

  const cookie = process.env.WEIBO_COOKIE?.trim() || readFirstFile([join(dataDir, "cookie.txt"), join(process.env.HOME ?? "", "weibo-mcp", "cookie.txt")]);
  if (!cookie) {
    warnOnStart(
      pi,
      `${SERVER_NAME} MCP 未注册：未找到 WEIBO_COOKIE。按 skills/${SERVER_NAME}-mcp/SKILL.md 配置（可放 ${join(dataDir, "cookie.txt")}），然后重开会话。`
    );
    return;
  }

  const runtime = pythonRuntime(dataDir, serverPy);
  if (!runtime) {
    warnOnStart(pi, `${SERVER_NAME} MCP 未注册：缺少 Python 环境。请运行 mcp/setup.sh ${NAME}，或安装 uv 后重开会话。`);
    return;
  }

  const env: Record<string, string> = { WEIBO_COOKIE: cookie };
  if (process.env.WEIBO_UID?.trim()) env.WEIBO_UID = process.env.WEIBO_UID.trim();

  pi.registerMcpServer(SERVER_NAME, {
    command: runtime.command,
    args: runtime.args,
    env,
    exposure: "deferred",
    description: "微博（只读：我的微博/搜索/长文/导出，Cookie 模式）",
  });
};
