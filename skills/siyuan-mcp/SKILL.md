---
name: siyuan-mcp
description: 配置/排查 TokenLens 的思源笔记 MCP（HTTP，本机 6806 端口）。当用户说“配置/安装/修复思源 MCP”“siyuan MCP 连不上/没有工具”“思源 token 无效”时使用。
---

# 思源笔记 MCP（siyuan-mcp）

思源笔记自带 HTTP MCP 服务，**没有本地代码**，默认由 `pi/extensions/siyuan-mcp/`
扩展注册（不要把 `siyuan` 写进 `mcp.json`；TokenLens 托管例外，见文末）。

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

## TokenLens 托管（可选，不配本机 token）

> v0.7.0 起扩展自动兜底：环境变量与本地文件都缺失时，执行
> `lens-agent secret get <NAME>` 从 TokenLens binding 取密钥（值不落盘）。
> 已接入配置同步的机器无需本机凭据或 `mcp.json` 条目；下面的显式写法只在需要
> 覆盖扩展注册（把接线放进 TokenLens 基线）时使用。

已接入 TokenLens 配置同步的机器可以改走 `mcp.json`（同名会覆盖扩展注册）：

```json
"siyuan": {
  "url": "http://127.0.0.1:6806/mcp",
  "headers": { "Authorization": "!lens-agent secret get --format 'Token {value}' SIYUAN_TOKEN" },
  "exposure": "deferred"
}
```

值在 Web「AI Agent → 机器部署 → 配置与密钥」按 binding 维护，多机用「复制全部密钥」
分发；本机需已配置 lens-agent 的 pi token。未迁移的机器保持扩展注册即可。

## 排障

- 启动提示“未找到 SIYUAN_TOKEN” → 回到步骤 2。
- 连接失败先 `curl -H 'Authorization: Token <token>' http://127.0.0.1:6806/api/system/version`
  验证思源与 token；远程实例注意防火墙。
- Token 在思源重启后不变；若更换工作空间需重新获取。
