---
name: outline-mcp
description: 配置/排查 TokenLens 的 Outline 知识库 MCP（npm 包 outline-mcp-server）。当用户说“配置/安装/修复 Outline MCP”“outline MCP 连不上/没有工具”“Outline API key 无效”时使用。
---

# Outline MCP（outline-mcp）

Outline 知识库 MCP，由 npm 包 `outline-mcp-server` 提供（无本仓库代码），
`pi/extensions/outline-mcp/` 扩展负责注册。不要把 `outline` 写进 `mcp.json`。

## 配置步骤

1. 在 Outline 里创建 API Token：设置 → API Tokens（记下 API URL，如
   `https://outline.example.com`）。

2. 写配置文件（或设 `OUTLINE_API_URL` / `OUTLINE_API_KEY` 环境变量）：

   ```bash
   mkdir -p ~/.local/share/token-lens-ex/mcp/outline
   cat > ~/.local/share/token-lens-ex/mcp/outline/config.json <<'EOF'
   { "apiUrl": "https://outline.example.com", "apiKey": "ol_api_xxx" }
   EOF
   chmod 600 ~/.local/share/token-lens-ex/mcp/outline/config.json
   ```

3. 机器需要 Node.js：扩展优先用 PATH 上的 `outline-mcp-server-stdio`（全局安装过
   就有），否则回退 `npx -y --package outline-mcp-server outline-mcp-server-stdio`。

4. 重开 pi 会话，确认 `outline` 工具可用。

## opencode 接入

`{file:}` 不能从 `config.json` 里取单个字段，所以把 URL / KEY 另存为两个小文件：

```bash
D=~/.local/share/token-lens-ex/mcp/outline
printf '%s' 'https://outline.example.com' > $D/api-url.txt
printf '%s' 'ol_api_xxx' > $D/api-key.txt
```

```jsonc
"outline": {
  "type": "local",
  "command": ["npx", "-y", "--package", "outline-mcp-server", "outline-mcp-server-stdio"],
  "environment": {
    "OUTLINE_API_URL": "{file:~/.local/share/token-lens-ex/mcp/outline/api-url.txt}",
    "OUTLINE_API_KEY": "{file:~/.local/share/token-lens-ex/mcp/outline/api-key.txt}"
  }
}
```

约定与排错见 token-lens-ex 的 `opencode/README.md`（`{file:}` 缺文件会让整份配置无效）。

## 排障

- 启动提示缺少 URL/KEY → 回到步骤 2。
- 提示需要 Node.js → 安装 Node（或 `npm i -g outline-mcp-server`）。
- 401/403 → 重新生成 API Token；确认 URL 末尾不要带 `/api`。
