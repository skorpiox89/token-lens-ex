---
name: siyuan-mcp
description: 配置/排查 TokenLens 的思源笔记 MCP（HTTP，本机 6806 端口）。当用户说“配置/安装/修复思源 MCP”“siyuan MCP 连不上/没有工具”“思源 token 无效”时使用。
---

# 思源笔记 MCP（siyuan-mcp）

思源笔记自带 HTTP MCP 服务，**没有本地代码**，由 `pi/extensions/siyuan-mcp/`
扩展注册（不要把 `siyuan` 写进 `mcp.json`）。

## 配置步骤

1. 思源里确认 MCP 可用：设置 → 关于 → API token（复制），并确保思源正在运行
   （默认 `http://127.0.0.1:6806`）。

2. 放 token（或设 `SIYUAN_TOKEN` 环境变量）：

   ```bash
   mkdir -p ~/.local/share/token-lens-ex/mcp/siyuan
   printf '%s\n' '<API token>' > ~/.local/share/token-lens-ex/mcp/siyuan/token.txt
   ```

3. 如果思源不在本机/端口不同：设置 `SIYUAN_MCP_URL`（如
   `http://192.168.1.10:6806/mcp`）。

4. 重开 pi 会话，确认 `siyuan` 工具可用。

## opencode 接入

`opencode.json` 里 token 不内联（远程地址按机器改）：

```jsonc
"siyuan": {
  "type": "remote",
  "url": "http://127.0.0.1:6806/mcp",
  "oauth": false,
  "headers": { "Authorization": "Token {file:~/.local/share/token-lens-ex/mcp/siyuan/token.txt}" }
}
```

约定与排错见 token-lens-ex 的 `opencode/README.md`（`{file:}` 缺文件会让整份配置无效）。

## 排障

- 启动提示“未找到 SIYUAN_TOKEN” → 回到步骤 2。
- 连接失败先 `curl -H 'Authorization: Token <token>' http://127.0.0.1:6806/api/system/version`
  验证思源与 token；远程实例注意防火墙。
- Token 在思源重启后不变；若更换工作空间需重新获取。
