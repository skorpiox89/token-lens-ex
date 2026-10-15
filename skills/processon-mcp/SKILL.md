---
name: processon-mcp
description: 配置/排查 TokenLens 的 ProcessOn MCP 服务（本地 cookie 模式）。当用户说“配置/安装/修复 ProcessOn MCP”“processon MCP 连不上/没有工具”“ProcessOn cookie 过期”时使用。
---

# ProcessOn MCP（processon-mcp）

只读 ProcessOn MCP（目录树/图表定义/Mermaid 转换/批量导出）。代码在 token-lens-ex
包的 `mcp/processon/`，由 `pi/extensions/processon-mcp/` 扩展**自动注册**——默认不要
把 `processon` 写进 `mcp.json`（TokenLens 托管例外，见文末）。

## 配置步骤

1. 建 Python 环境：

   ```bash
   sh <包目录>/mcp/setup.sh processon
   ```

2. 放 cookie（或设 `PROCESSON_COOKIE` 环境变量）：

   ```bash
   mkdir -p ~/.local/share/token-lens-ex/mcp/processon
   vi ~/.local/share/token-lens-ex/mcp/processon/cookie.txt
   ```

   **获取 cookie**：浏览器登录 processon.com → F12 → Network → 刷新 → 任意请求的
   Request Headers 里整段复制 `Cookie:` 的值。也支持账号密码模式
   （`PROCESSON_ACCOUNT` / `PROCESSON_PASSWORD` 环境变量）。

3. 校验：

   ```bash
   python3 <包目录>/mcp/processon/check_cookie.py
   ```

4. 重开 pi 会话，确认 `processon` 工具可用。

## opencode 接入

`opencode.json` 里零明文、零本机绝对路径（先跑 `setup.sh` 生成 `run.sh`）：

```jsonc
"processon": {
  "type": "local",
  "command": ["{env:HOME}/.local/share/token-lens-ex/mcp/processon/run.sh"],
  "environment": { "PROCESSON_COOKIE": "{file:~/.local/share/token-lens-ex/mcp/processon/cookie.txt}" }
}
```

约定与排错见 token-lens-ex 的 `opencode/README.md`（`{file:}` 缺文件会让整份配置无效）。

## TokenLens 托管（可选，不配本机 cookie）

> v0.7.0 起扩展自动兜底：环境变量与本地文件都缺失时，执行
> `lens-agent secret get <NAME>` 从 TokenLens binding 取密钥（值不落盘）。
> 已接入配置同步的机器无需本机凭据或 `mcp.json` 条目；下面的显式写法只在需要
> 覆盖扩展注册（把接线放进 TokenLens 基线）时使用。

已接入 TokenLens 配置同步的机器可以改走 `mcp.json`（先跑过 `setup.sh`；同名覆盖
扩展注册）：

```json
"processon": {
  "command": "~/.local/share/token-lens-ex/mcp/processon/run.sh",
  "env": { "PROCESSON_COOKIE": "!lens-agent secret get PROCESSON_COOKIE" },
  "exposure": "deferred"
}
```

值在 Web「AI Agent → 机器部署 → 配置与密钥」按 binding 维护，多机用「复制全部密钥」
分发；未迁移的机器保持扩展注册即可。

## 排障

- 启动提示缺少凭据 → 回到步骤 2；提示缺 Python 环境 → 步骤 1。
- cookie 模式失效时也可改用账号密码（扩展会一并传入）。
- 兼容旧路径 `~/processon-mcp/cookie.txt`。
