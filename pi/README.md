# pi 资源

pi 专用的扩展与技能。根 `package.json` 的 `pi` 字段指向这里：

```json
"pi": {
  "extensions": ["./pi/extensions/*/index.ts"],
  "skills": ["./skills", "./pi/skills"]
}
```

- `extensions/<name>/`：pi 扩展，入口 `index.ts`（可选 `package.json` 声明 `pi.extensions`）；
  新增后无需改根清单，`*` 会自动匹配。
- `skills/<name>/SKILL.md`：pi 专用技能；跨 agent 通用技能放仓库根的 `skills/`。

安装（在 pi 里）：

```bash
pi install git:github.com/skorpiox89/token-lens-ex@v0.2.0
pi list          # 确认加载
```

当前扩展：

- `pi-token-lens-ttft`：把每条 assistant 请求的 TTFT 写入 pi 会话 JSONL，供
  TokenLens 的 `lens-agent` 采集为使用记录的 `first_token_ms`。
- `yuque-mcp`：自动注册包内 `mcp/yuque/` 的语雀 MCP server（配置即代码，
  不依赖 `mcp.json`）；环境与 cookie 处理见 `skills/yuque-mcp/SKILL.md`。
