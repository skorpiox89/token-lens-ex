import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { hasExecutable, lensAgentSecret, mcpDataDir, warnOnStart } from "../lib/mcp-support.ts";

/**
 * outline-mcp：注册 Outline 知识库 MCP（npm 包 outline-mcp-server，无本地代码）。
 * 凭据：OUTLINE_API_URL / OUTLINE_API_KEY 环境变量 → 数据目录 config.json
 * → TokenLens binding 密钥。
 * 命令：优先 PATH 上的 outline-mcp-server-stdio（全局安装），否则 npx 拉取。
 */

const SERVER_NAME = "outline";
const dataDir = mcpDataDir(SERVER_NAME);

interface OutlineConfig {
  apiUrl?: string;
  apiKey?: string;
}

function readConfigFile(): OutlineConfig {
  for (const name of ["config.json", "outline.json"]) {
    try {
      const parsed = JSON.parse(readFileSync(join(dataDir, name), "utf8")) as OutlineConfig;
      if (parsed.apiUrl || parsed.apiKey) return parsed;
    } catch {
      // 尝试下一个
    }
  }
  return {};
}

export default (pi: ExtensionAPI) => {
  const fileConfig = readConfigFile();
  const apiUrl =
    process.env.OUTLINE_API_URL?.trim() ||
    fileConfig.apiUrl?.trim() ||
    lensAgentSecret("OUTLINE_API_URL");
  const apiKey =
    process.env.OUTLINE_API_KEY?.trim() ||
    fileConfig.apiKey?.trim() ||
    lensAgentSecret("OUTLINE_API_KEY");
  if (!apiUrl || !apiKey) {
    warnOnStart(
      pi,
      `${SERVER_NAME} MCP 未注册：缺少 OUTLINE_API_URL / OUTLINE_API_KEY。按 skills/${SERVER_NAME}-mcp/SKILL.md 配置（可放 ${join(dataDir, "config.json")}），然后重开会话。`
    );
    return;
  }

  const stdioBin = process.platform === "win32" ? "outline-mcp-server-stdio.cmd" : "outline-mcp-server-stdio";
  let command: string;
  let args: string[];
  if (hasExecutable(stdioBin)) {
    command = stdioBin;
    args = [];
  } else if (hasExecutable(process.platform === "win32" ? "npx.cmd" : "npx")) {
    command = process.platform === "win32" ? "npx.cmd" : "npx";
    args = ["-y", "--package", "outline-mcp-server", "outline-mcp-server-stdio"];
  } else {
    warnOnStart(pi, `${SERVER_NAME} MCP 未注册：需要 Node.js（outline-mcp-server-stdio 或 npx）。`);
    return;
  }

  pi.registerMcpServer(SERVER_NAME, {
    command,
    args,
    env: { OUTLINE_API_URL: apiUrl, OUTLINE_API_KEY: apiKey },
    exposure: "deferred",
    description: "本地 Outline 知识库（文档/集合/评论/用户）",
  });
};
