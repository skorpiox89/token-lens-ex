# token-lens-ex

TokenLens 的 AI Agent 资源仓库（ex = extensions / skills）：集中存放各 AI agent
的扩展与技能。同一个仓库同时承载多种 agent 的资源，各自从仓库里安装/发现自己
需要的部分。

## 目录结构

```
.
├── package.json                # pi 包清单（pi.extensions / pi.skills）
├── extensions/                 # pi 扩展：每个子目录一个，入口 index.ts
│   └── pi-token-lens-ttft/     # 把 TTFT 写入 pi 会话 JSONL，供 lens-agent 采集
└── skills/                     # 通用 Agent Skills（每个技能一个含 SKILL.md 的目录）
```

- `extensions/`、`package.json` 的 `pi` 字段是 pi 专用的。
- `skills/` 遵循 Agent Skills 规范，pi / opencode / codex 等都可以使用；后续可按
  agent 增加各自的插件目录（如 `opencode/`、`codex/`），互不影响。

## pi 安装

```bash
# 固定 tag（推荐）
pi install git:github.com/skorpiox89/token-lens-ex@v0.1.1

# 本地开发
pi install /path/to/token-lens-ex
```

- git 包按 tag/commit 固定，不会自动跟随分支更新。
- 升级到新版本：把 settings 里的 ref 改成新 tag，然后 `pi update --extensions`。
- 卸载：`pi remove git:github.com/skorpiox89/token-lens-ex`。
- 安装后启动 pi，用 `pi list` 或启动横幅里的 `[Extensions]` 确认资源已加载。

## 发布新版本

1. 修改 `extensions/` 或 `skills/` 下的资源；
2. 更新根 `package.json` 的 `version`；
3. `git tag vX.Y.Z && git push origin vX.Y.Z`；
4. 各机器把安装 ref 指向新 tag。

## 资源说明

- `pi-token-lens-ttft`：记录每条 assistant 请求的 TTFT 到 pi 会话 JSONL，
  TokenLens 的 `lens-agent` 采集后写入使用明细的 `first_token_ms`。
  详见 [`extensions/pi-token-lens-ttft/README.md`](extensions/pi-token-lens-ttft/README.md)。
