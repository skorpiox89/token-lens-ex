---
name: qzone-mcp
description: 配置/排查 TokenLens 的 QQ空间 MCP 服务（本地 cookie 模式）。当用户说“配置/安装/修复QQ空间 MCP”“qzone MCP 连不上/没有工具”“QQ空间 cookie 过期”时使用。
---

# QQ空间 MCP（qzone-mcp）

只读 QQ空间 MCP（说说/日志/相册）。代码在 token-lens-ex 包的 `mcp/qzone/`，
由 `pi/extensions/qzone-mcp/` 扩展**自动注册**——默认不要把 `qzone` 写进 `mcp.json`
（TokenLens 托管例外，见文末）。

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

## opencode 接入

`opencode.json` 里零明文、零本机绝对路径（先跑 `setup.sh` 生成 `run.sh`）：

```jsonc
"qzone": {
  "type": "local",
  "command": ["{env:HOME}/.local/share/token-lens-ex/mcp/qzone/run.sh"],
  "environment": { "QZONE_COOKIE": "{file:~/.local/share/token-lens-ex/mcp/qzone/cookie.txt}" }
}
```

约定与排错见 token-lens-ex 的 `opencode/README.md`（`{file:}` 缺文件会让整份配置无效）。

## TokenLens 托管（可选，不配本机 cookie）

已接入 TokenLens 配置同步的机器可以改走 `mcp.json`（先跑过 `setup.sh`；同名覆盖
扩展注册）：

```json
"qzone": {
  "command": "~/.local/share/token-lens-ex/mcp/qzone/run.sh",
  "env": { "QZONE_COOKIE": "!lens-agent secret get QZONE_COOKIE" },
  "exposure": "deferred"
}
```

值在 Web「AI Agent → 机器部署 → 配置与密钥」按 binding 维护，多机用「复制全部密钥」
分发；未迁移的机器保持扩展注册即可。

## 排障

- 启动提示“未找到 QZONE_COOKIE” → 回到步骤 2；提示缺 Python 环境 → 步骤 1。
- 校验报 “cookie 中没有 p_skey/skey” → 复制时漏了 cookie 段，重新整段复制。
- 兼容旧路径 `~/qzone-mcp/cookie.txt`。
