---
name: processon-mcp
description: 配置/排查 TokenLens 的 ProcessOn MCP 服务（本地 cookie 模式）。当用户说“配置/安装/修复 ProcessOn MCP”“processon MCP 连不上/没有工具”“ProcessOn cookie 过期”时使用。
---

# ProcessOn MCP（processon-mcp）

只读 ProcessOn MCP（目录树/图表定义/Mermaid 转换/批量导出）。代码在 token-lens-ex
包的 `mcp/processon/`，由 `pi/extensions/processon-mcp/` 扩展**自动注册**——不要
把 `processon` 写进 `mcp.json`。

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

## 排障

- 启动提示缺少凭据 → 回到步骤 2；提示缺 Python 环境 → 步骤 1。
- cookie 模式失效时也可改用账号密码（扩展会一并传入）。
- 兼容旧路径 `~/processon-mcp/cookie.txt`。
