---
name: qzone-mcp
description: 配置/排查 TokenLens 的 QQ空间 MCP 服务（本地 cookie 模式）。当用户说“配置/安装/修复QQ空间 MCP”“qzone MCP 连不上/没有工具”“QQ空间 cookie 过期”时使用。
---

# QQ空间 MCP（qzone-mcp）

只读 QQ空间 MCP（说说/日志/相册）。代码在 token-lens-ex 包的 `mcp/qzone/`，
由 `pi/extensions/qzone-mcp/` 扩展**自动注册**——不要把 `qzone` 写进 `mcp.json`。

## 配置步骤

1. 建 Python 环境：

   ```bash
   sh <包目录>/mcp/setup.sh qzone
   ```

2. 放 cookie（或设 `QZONE_COOKIE` 环境变量）：

   ```bash
   mkdir -p ~/.local/share/token-lens-ex/mcp/qzone
   vi ~/.local/share/token-lens-ex/mcp/qzone/cookie.txt
   ```

   **获取 cookie**：浏览器登录 user.qzone.qq.com → F12 → Network → 刷新 → 任意请求的
   Request Headers 里整段复制 `Cookie:` 的值（需包含 `uin`、`p_skey`/`skey`）。

3. 校验：

   ```bash
   python3 <包目录>/mcp/qzone/check_cookie.py
   ```

4. 重开 pi 会话，确认 `qzone` 工具可用。

## 排障

- 启动提示“未找到 QZONE_COOKIE” → 回到步骤 2；提示缺 Python 环境 → 步骤 1。
- 校验报 “cookie 中没有 p_skey/skey” → 复制时漏了 cookie 段，重新整段复制。
- 兼容旧路径 `~/qzone-mcp/cookie.txt`。
