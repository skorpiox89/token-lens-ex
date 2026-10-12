# 思源笔记 MCP（siyuan）

思源笔记自带 MCP 服务（HTTP），**没有本地代码**，只需注册地址与 API Token：

| 项 | 值 |
|---|---|
| URL | `http://127.0.0.1:6806/mcp`（可用 `SIYUAN_MCP_URL` 覆盖，如远程实例） |
| Token | 思源「设置 → 关于 → API token」，写入 `~/.local/share/token-lens-ex/mcp/siyuan/token.txt` 或设 `SIYUAN_TOKEN` |

注册由 `pi/extensions/siyuan-mcp/` 扩展完成（`pi.registerMcpServer`），不需要在
`mcp.json` 里维护条目。配置方法见 `skills/siyuan-mcp/SKILL.md`。
