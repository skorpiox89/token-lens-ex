---
name: weibo-mcp
description: 配置/排查 TokenLens 的微博 MCP 服务（本地 cookie 模式）。当用户说“配置/安装/修复微博 MCP”“微博 MCP 连不上/没有工具”“微博 cookie 过期”时使用。
---

# 微博 MCP（weibo-mcp）

只读微博 MCP（我的微博/搜索/长文/导出）。代码在 token-lens-ex 包的 `mcp/weibo/`，
由 `pi/extensions/weibo-mcp/` 扩展**自动注册**——不要把 `weibo` 写进 `mcp.json`。

## 配置步骤

1. 建 Python 环境（包目录下）：

   ```bash
   sh <包目录>/mcp/setup.sh weibo
   ```

2. 放 cookie 到数据目录（或设 `WEIBO_COOKIE` 环境变量）：

   ```bash
   mkdir -p ~/.local/share/token-lens-ex/mcp/weibo
   vi ~/.local/share/token-lens-ex/mcp/weibo/cookie.txt
   ```

   **获取 cookie**：浏览器登录 weibo.com → F12 → Network → 刷新 → 任意请求的
   Request Headers 里整段复制 `Cookie:` 的值。

3. 校验：

   ```bash
   python3 <包目录>/mcp/weibo/check_cookie.py
   ```

4. 重开 pi 会话，确认 `weibo` 工具可用。

## opencode 接入

`opencode.json` 里零明文、零本机绝对路径（先跑 `setup.sh` 生成 `run.sh`）：

```jsonc
"weibo": {
  "type": "local",
  "command": ["{env:HOME}/.local/share/token-lens-ex/mcp/weibo/run.sh"],
  "environment": { "WEIBO_COOKIE": "{file:~/.local/share/token-lens-ex/mcp/weibo/cookie.txt}" }
}
```

约定与排错见 token-lens-ex 的 `opencode/README.md`（`{file:}` 缺文件会让整份配置无效）。

## 排障

- 启动提示“未找到 WEIBO_COOKIE” → 回到步骤 2；提示缺 Python 环境 → 步骤 1。
- cookie 失效（微博改版/过期）→ 重新复制；可选 `WEIBO_UID` 环境变量指定 uid。
- 兼容旧路径 `~/weibo-mcp/cookie.txt`（无需改动即可用）。
