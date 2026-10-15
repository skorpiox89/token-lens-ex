---
name: outline-mcp
description: 配置/排查 TokenLens 的 Outline 知识库 MCP（npm 包 outline-mcp-server）。当用户说“配置/安装/修复 Outline MCP”“outline MCP 连不上/没有工具”“Outline API key 无效”时使用。
---

# Outline MCP（outline-mcp）

Outline 知识库 MCP，由 npm 包 `outline-mcp-server` 提供（无本仓库代码），
`pi/extensions/outline-mcp/` 扩展负责注册。默认不要把 `outline` 写进 `mcp.json`
（TokenLens 托管例外，见文末）。

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

## TokenLens 托管（可选，不配本机 key）

> v0.7.0 起扩展自动兜底：环境变量与本地文件都缺失时，执行
> `lens-agent secret get <NAME>` 从 TokenLens binding 取密钥（值不落盘）。
> 已接入配置同步的机器无需本机凭据或 `mcp.json` 条目；下面的显式写法只在需要
> 覆盖扩展注册（把接线放进 TokenLens 基线）时使用。

已接入 TokenLens 配置同步的机器可以改走 `mcp.json`（同名覆盖扩展注册）：

```json
"outline": {
  "command": "npx",
  "args": ["-y", "--package", "outline-mcp-server", "outline-mcp-server-stdio"],
  "env": {
    "OUTLINE_API_URL": "https://outline.example.com",
    "OUTLINE_API_KEY": "!lens-agent secret get OUTLINE_API_KEY"
  },
  "exposure": "deferred"
}
```

`OUTLINE_API_URL` 不是秘密、按机器写；key 在 Web「AI Agent → 机器部署 → 配置与密钥」
按 binding 维护，多机用「复制全部密钥」分发。

## 排障

- 启动提示缺少 URL/KEY → 回到步骤 2。
- 提示需要 Node.js → 安装 Node（或 `npm i -g outline-mcp-server`）。
- 401/403 → 重新生成 API Token；确认 URL 末尾不要带 `/api`。
