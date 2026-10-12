# Outline MCP（outline）

Outline 知识库 MCP，由 npm 包 `outline-mcp-server` 提供（**没有本仓库代码**）。
扩展用 `npx -y outline-mcp-server` 启动，凭据从环境变量或数据目录读取：

| 项 | 值 |
|---|---|
| URL | `OUTLINE_API_URL`（如 `https://outline.example.com`） |
| API Key | `OUTLINE_API_KEY`（Outline「设置 → API Tokens」创建） |
| 数据文件 | `~/.local/share/token-lens-ex/mcp/outline/config.json`：`{ "apiUrl": "...", "apiKey": "..." }` |

注册由 `pi/extensions/outline-mcp/` 扩展完成，不需要在 `mcp.json` 里维护条目。
依赖：机器上有 Node.js / `npx` 可用。配置方法见 `skills/outline-mcp/SKILL.md`。
