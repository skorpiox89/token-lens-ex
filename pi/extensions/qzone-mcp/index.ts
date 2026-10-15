import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { mcpDataDir, firstSecret, packageRoot, pythonRuntime, warnOnStart } from "../lib/mcp-support.ts";

/**
 * qzone-mcp：注册包内 mcp/qzone/server.py 为 pi 的 MCP server（配置即代码）。
 * cookie：QZONE_COOKIE 环境变量 → 数据目录 cookie.txt → ~/qzone-mcp/cookie.txt
 * → TokenLens binding 密钥。
 */

const NAME = "qzone";
const SERVER_NAME = "qzone";
const dataDir = mcpDataDir(NAME);
const serverPy = join(packageRoot(import.meta.url), "mcp", NAME, "server.py");

export default (pi: ExtensionAPI) => {
  if (!existsSync(serverPy)) {
    warnOnStart(pi, `${SERVER_NAME} MCP：包内缺少 ${serverPy}，请更新 token-lens-ex 包。`);
    return;
  }

  const cookie = firstSecret("QZONE_COOKIE", process.env.QZONE_COOKIE, [
    join(dataDir, "cookie.txt"),
    join(homedir(), "qzone-mcp", "cookie.txt"),
  ]);
  if (!cookie) {
    warnOnStart(
      pi,
      `${SERVER_NAME} MCP 未注册：未找到 QZONE_COOKIE。按 skills/${SERVER_NAME}-mcp/SKILL.md 配置（可放 ${join(dataDir, "cookie.txt")}），然后重开会话。`
    );
    return;
  }

  const runtime = pythonRuntime(dataDir, serverPy);
  if (!runtime) {
    warnOnStart(pi, `${SERVER_NAME} MCP 未注册：缺少 Python 环境。请运行 mcp/setup.sh ${NAME}，或安装 uv 后重开会话。`);
    return;
  }

  pi.registerMcpServer(SERVER_NAME, {
    command: runtime.command,
    args: runtime.args,
    env: { QZONE_COOKIE: cookie },
    exposure: "deferred",
    description: "QQ空间（只读：说说/日志/相册，Cookie 模式）",
  });
};
