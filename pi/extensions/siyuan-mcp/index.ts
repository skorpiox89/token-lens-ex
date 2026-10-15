import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { mcpDataDir, firstSecret, warnOnStart } from "../lib/mcp-support.ts";

/**
 * siyuan-mcp：注册思源笔记自带的 HTTP MCP 服务（无本地代码）。
 * URL：SIYUAN_MCP_URL 环境变量，默认 http://127.0.0.1:6806/mcp。
 * Token：SIYUAN_TOKEN 环境变量 → 数据目录 token.txt → TokenLens binding 密钥。
 */

const SERVER_NAME = "siyuan";
const dataDir = mcpDataDir(SERVER_NAME);

export default (pi: ExtensionAPI) => {
  const url = process.env.SIYUAN_MCP_URL?.trim() || "http://127.0.0.1:6806/mcp";
  const token = firstSecret("SIYUAN_TOKEN", process.env.SIYUAN_TOKEN, [join(dataDir, "token.txt")]);
  if (!token) {
    warnOnStart(
      pi,
      `${SERVER_NAME} MCP 未注册：未找到 SIYUAN_TOKEN。按 skills/${SERVER_NAME}-mcp/SKILL.md 配置（可放 ${join(dataDir, "token.txt")}），然后重开会话。`
    );
    return;
  }

  pi.registerMcpServer(SERVER_NAME, {
    url,
    headers: { Authorization: `Token ${token}` },
    exposure: "deferred",
    description: "思源笔记（本地知识库：文档/块/搜索/SQL/属性视图/导出）",
  });
};
