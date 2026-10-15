import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { mcpDataDir, firstSecret, lensAgentSecret, packageRoot, pythonRuntime, warnOnStart } from "../lib/mcp-support.ts";

/**
 * yuque-mcp：注册包内 mcp/yuque/server.py 为 pi 的 MCP server（配置即代码）。
 * cookie：YUQUE_COOKIE 环境变量 → 数据目录 cookie.txt → ~/yuque-mcp/cookie.txt；
 * YUQUE_TOKEN（官方 API）优先；两者都缺时回退 TokenLens binding 密钥。
 */

const NAME = "yuque";
const SERVER_NAME = "yuque";
const dataDir = mcpDataDir(NAME);
const serverPy = join(packageRoot(import.meta.url), "mcp", NAME, "server.py");

export default (pi: ExtensionAPI) => {
  if (!existsSync(serverPy)) {
    warnOnStart(pi, `${SERVER_NAME} MCP：包内缺少 ${serverPy}，请更新 token-lens-ex 包。`);
    return;
  }

  const token = process.env.YUQUE_TOKEN?.trim() || lensAgentSecret("YUQUE_TOKEN");
  const cookie = firstSecret("YUQUE_COOKIE", process.env.YUQUE_COOKIE, [
    join(dataDir, "cookie.txt"),
    join(homedir(), "yuque-mcp", "cookie.txt"),
  ]);
  if (!token && !cookie) {
    warnOnStart(
      pi,
      `${SERVER_NAME} MCP 未注册：未找到 YUQUE_TOKEN / YUQUE_COOKIE。按 skills/${SERVER_NAME}-mcp/SKILL.md 配置（cookie 可放 ${join(dataDir, "cookie.txt")}），然后重开会话。`
    );
    return;
  }

  const runtime = pythonRuntime(dataDir, serverPy);
  if (!runtime) {
    warnOnStart(pi, `${SERVER_NAME} MCP 未注册：缺少 Python 环境。请运行 mcp/setup.sh ${NAME}，或安装 uv 后重开会话。`);
    return;
  }

  const env: Record<string, string> = { YUQUE_LOGIN: process.env.YUQUE_LOGIN?.trim() || "huangxuantao" };
  if (token) env.YUQUE_TOKEN = token;
  if (cookie) env.YUQUE_COOKIE = cookie;

  pi.registerMcpServer(SERVER_NAME, {
    command: runtime.command,
    args: runtime.args,
    env,
    exposure: "deferred",
    description: "语雀知识库（本地 Cookie 模式，无需会员；文档/知识库读写）",
  });
};
