# MCP 服务（MCP-as-code）

这里的 MCP 服务代码不通过 `mcp.json` 分发（配置与环境无法跨机直接同步），而是：

1. **代码**放本目录 `mcp/<name>/`，随 pi 包（token-lens-ex）一起安装到各机器；
2. **自动注册**由 `pi/extensions/<name>-mcp/` 扩展负责：用 `pi.registerMcpServer()`
   注册，路径相对包目录解析，环境缺失时给出提示；
3. **知识/人工步骤**写进 `skills/<name>-mcp/SKILL.md`，ai agent 可按需执行
   （装依赖、放 cookie、验证）；
4. **秘密**（cookie/token）只留在机器上（环境变量或数据目录文件），永不进仓库。

新增一个 MCP 服务时：

- `mcp/<name>/`：服务代码 + `requirements.txt`（或 package.json）+ `setup.sh`；
- `pi/extensions/<name>-mcp/index.ts`：注册扩展；
- `skills/<name>-mcp/SKILL.md`：部署与排障说明。

纯配置型（无本地代码、直连 URL）的 MCP 仍可放在 `mcp.json`，由 TokenLens 基线同步。
