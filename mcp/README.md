# MCP 服务（MCP-as-code）

这里的 MCP 服务代码不通过 `mcp.json` 分发（配置与环境无法跨机直接同步），而是：

1. **代码**放本目录 `mcp/<name>/`，随 pi 包（token-lens-ex）一起安装到各机器；
2. **自动注册**由 `pi/extensions/<name>-mcp/` 扩展负责：用 `pi.registerMcpServer()`
   注册，路径相对包目录解析，环境缺失时给出提示；
3. **知识/人工步骤**写进 `skills/<name>-mcp/SKILL.md`，ai agent 可按需执行
   （装依赖、放 cookie、验证）；
4. **秘密**（cookie/token）只留在机器上（环境变量或数据目录文件），永不进仓库。

新增一个 MCP 服务时：

- `mcp/<name>/`：服务代码 + `requirements.txt`（或 package.json）+ `check_cookie.py`；
- `pi/extensions/<name>-mcp/index.ts`：注册扩展（用 `../lib/mcp-support.ts` 的共享工具）；
- `skills/<name>-mcp/SKILL.md`：部署与排障说明。

环境准备统一用 `sh mcp/setup.sh <name>`：venv 建在数据目录（不在包内），同时生成
机器本地启动器 `~/.local/share/token-lens-ex/mcp/<name>/run.sh`。
pi 扩展直接按包内路径解析；没有包机制的客户端（如 opencode）统一调用 `run.sh`，
详见 [`../opencode/README.md`](../opencode/README.md)。

当前服务：

| 服务 | 类型 | 凭据 |
|---|---|---|
| `yuque` | Python stdio | `YUQUE_COOKIE`（或 `YUQUE_TOKEN`） |
| `weibo` | Python stdio | `WEIBO_COOKIE` |
| `qzone` | Python stdio | `QZONE_COOKIE` |
| `processon` | Python stdio | `PROCESSON_COOKIE`（或账号密码） |
| `siyuan` | HTTP（思源自带） | `SIYUAN_TOKEN` + `SIYUAN_MCP_URL` |
| `outline` | npm stdio（`outline-mcp-server`） | `OUTLINE_API_URL` + `OUTLINE_API_KEY` |

凭据统一放 `~/.local/share/token-lens-ex/mcp/<name>/`（cookie.txt / token.txt / config.json）
或对应环境变量；兼容旧的 `~/<name>-mcp/` 路径。

纯配置型（无本地代码、直连 URL）的 MCP 仍可放在 `mcp.json`，由 TokenLens 基线同步。
