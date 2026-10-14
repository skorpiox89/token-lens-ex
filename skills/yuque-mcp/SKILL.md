---
name: yuque-mcp
description: 配置/排查 TokenLens 的语雀 MCP 服务（本地 cookie 模式）。当用户说“配置/安装/修复语雀 MCP”“语雀 MCP 连不上/没有工具”“cookie 过期”时使用。
---

# 语雀 MCP（yuque-mcp）

语雀知识库读写的本地 stdio MCP 服务。代码在 token-lens-ex 包的 `mcp/yuque/`，
由 `pi/extensions/yuque-mcp/` 扩展 **自动注册**——默认**不要**往 `mcp.json` 里写
`yuque` 条目（同名会覆盖扩展注册，造成两份配置；TokenLens 托管是有意覆盖，见文末）。

## 组成与路径

| 内容 | 路径 |
|---|---|
| 服务代码 | 包内 `mcp/yuque/server.py`（随 pi 包安装） |
| 注册扩展 | 包内 `pi/extensions/yuque-mcp/index.ts` |
| Python 环境（venv） | `~/.local/share/token-lens-ex/mcp/yuque/venv` |
| cookie（秘密） | `~/.local/share/token-lens-ex/mcp/yuque/cookie.txt` 或 `YUQUE_COOKIE` 环境变量 |

扩展的查找顺序：`YUQUE_TOKEN` 环境变量（官方 API，需会员）优先；否则
`YUQUE_COOKIE` 环境变量 → 数据目录 `cookie.txt` → `~/yuque-mcp/cookie.txt`（旧路径）。
运行环境：数据目录 venv 优先；没有 venv 且系统有 `uv` 时回退 `uv run --with 'mcp>=1.2.0,<2'`。

## 在新机器上配置（按顺序执行）

1. 找到包目录（`pi list` 里的 git 包路径，如 `~/.pi/agent/git/github.com/skorpiox89/token-lens-ex`），执行：

   ```bash
   sh <包目录>/mcp/setup.sh yuque
   ```

   需要 `python3`；也可以改用 `uv`（不建 venv 时扩展会自动用 uv）。

2. 准备 cookie（二选一）：

   - 文件方式（推荐）：

     ```bash
     mkdir -p ~/.local/share/token-lens-ex/mcp/yuque
     # 把下面命令的输出粘到 cookie.txt（从浏览器获取，见下）
     vi ~/.local/share/token-lens-ex/mcp/yuque/cookie.txt
     ```

   - 环境变量方式：在 shell/systemd 里设置 `YUQUE_COOKIE="..."`。

   **获取 cookie**：浏览器打开语雀并登录 → F12 → Network → 刷新页面 → 点任意请求 →
   Request Headers 里整段复制 `Cookie:` 的值（需包含 `_yuque_session` 与 `yuque_ctoken`）。
   有效期约 2 周，过期后重新复制。

3. 校验 cookie：

   ```bash
   python3 <包目录>/mcp/yuque/check_cookie.py
   ```

4. 重开 pi 会话（或 `/reload`），用 `/mcp` 或工具搜索确认 `yuque` 已连接。
   扩展注册无需写入任何配置文件。

## opencode 接入

`opencode.json` 里零明文、零本机绝对路径（先跑 `setup.sh` 生成 `run.sh`）：

```jsonc
"yuque": {
  "type": "local",
  "command": ["{env:HOME}/.local/share/token-lens-ex/mcp/yuque/run.sh"],
  "environment": {
    "YUQUE_COOKIE": "{file:~/.local/share/token-lens-ex/mcp/yuque/cookie.txt}",
    "YUQUE_LOGIN": "<你的语雀登录名>"
  }
}
```

约定与排错见 token-lens-ex 的 `opencode/README.md`（`{file:}` 缺文件会让整份配置无效）。

## TokenLens 托管（可选，不配本机 cookie）

已接入 TokenLens 配置同步的机器可以改走 `mcp.json`（先跑过 `setup.sh`；同名覆盖
扩展注册）：

```json
"yuque": {
  "command": "~/.local/share/token-lens-ex/mcp/yuque/run.sh",
  "env": { "YUQUE_COOKIE": "!lens-agent secret get YUQUE_COOKIE" },
  "exposure": "deferred"
}
```

值在 Web「AI Agent → 机器部署 → 配置与密钥」按 binding 维护，多机用「复制全部密钥」
分发；未迁移的机器保持扩展注册即可。

## 排障

- **没有 yuque 工具**：重开会话；若启动提示“未找到 YUQUE_TOKEN / YUQUE_COOKIE”，回到步骤 2；
  若提示缺少 Python 环境，回到步骤 1。
- **cookie 失效**：跑 `check_cookie.py` 确认后重新复制（HTTP 401/403）。
- **想临时禁用**：在 `mcp.json` 写 `"yuque": { "enabled": false }`（仅覆盖开关，不会覆盖扩展的
  服务器定义）；长期禁用则卸载包或删除本技能。
- **调试服务本身**：`test_client.py` 可做协议级自测：

  ```bash
  V=~/.local/share/token-lens-ex/mcp/yuque/venv
  YUQUE_COOKIE="$(cat ~/.local/share/token-lens-ex/mcp/yuque/cookie.txt)" "$V/bin/python" <包目录>/mcp/yuque/test_client.py
  ```
