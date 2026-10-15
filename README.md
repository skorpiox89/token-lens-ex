# token-lens-ex

TokenLens 的 AI Agent 资源仓库（ex = extensions / plugins / skills）：集中存放各家
AI agent 的扩展与技能。**每个 agent 一个顶层目录**，互不干扰；跨 agent 的通用技能
放在根 `skills/`。

## 目录结构

```
token-lens-ex/
├── package.json                 # pi 包清单（pi.extensions / pi.skills）
├── .agents/plugins/
│   └── marketplace.json         # Codex marketplace 清单（有 codex 插件时启用）
├── skills/                      # 跨 agent 通用技能（Agent Skills 规范，SKILL.md）
├── mcp/                         # MCP 服务代码（MCP-as-code，见下）
│   ├── yuque/ weibo/ qzone/ processon/   # 本地 stdio 服务（Python）
│   ├── siyuan/                  # 无代码：登记思源 HTTP MCP 的说明
│   └── setup.sh                 # 建 venv：./setup.sh <name>
├── pi/                          # pi 专用
│   ├── extensions/              # pi 扩展：每个子目录一个，入口 index.ts
│   │   ├── pi-token-lens-ttft/
│   │   ├── yuque-mcp/           # 以下 5 个自动注册对应 MCP server
│   │   ├── weibo-mcp/ qzone-mcp/ processon-mcp/ siyuan-mcp/
│   │   └── lib/                 # 扩展共享工具（不被当扩展加载）
│   └── skills/                  # pi 专用技能
├── codex/                       # Codex 专用
│   └── plugins/                 # Codex 插件：每个子目录一个，含 .codex-plugin/plugin.json
└── opencode/                    # opencode 专用
    ├── README.md                # MCP 配置约定：零明文秘密、零本机绝对路径
    └── plugins/                 # opencode 插件（预留）
```

## 各家 agent 的接入方式

| agent | 安装/发现方式 | 资源放哪 |
|---|---|---|
| **pi** | `pi install git:github.com/skorpiox89/token-lens-ex@vX.Y.Z`（读根 `package.json` 的 `pi` 字段） | `pi/extensions/*/index.ts`、`pi/skills/`、根 `skills/` |
| **codex** | `codex plugin marketplace add skorpiox89/token-lens-ex@vX.Y.Z` + `codex plugin add <name>`（读根 `.agents/plugins/marketplace.json`） | `codex/plugins/<name>/`（其中 skills 放插件的 `skills/` 下） |
| **opencode** | 插件：`opencode plugin add github:skorpiox89/token-lens-ex`（npm/git 包以仓库根为单位）；MCP：写 `opencode.json`，按 [`opencode/README.md`](opencode/README.md) 用 `{file:}`/`{env:HOME}` 零明文引用 | `opencode/plugins/<name>/`（由 `opencode/index.ts` 统一 re-export）；本机资源在数据目录 |
| 其他 | 按各自规范，新增顶层目录（如 `cline/`）并在对应清单里注册 | — |

### pi

```bash
pi install git:github.com/skorpiox89/token-lens-ex@v0.5.0   # 固定 tag，推荐
pi install /path/to/token-lens-ex                            # 本地开发
```

- git 包按 tag/commit 固定，升级需改 ref 后 `pi update --extensions`；卸载 `pi remove git:github.com/skorpiox89/token-lens-ex`。
- 新增 pi 扩展：在 `pi/extensions/<name>/` 放 `index.ts`（可选 `package.json`），根 `package.json` 的 `pi.extensions` 是 `./pi/extensions/*/index.ts`，无需再改。

### codex（预留）

仓库根放 `.agents/plugins/marketplace.json`，每个插件在 `codex/plugins/<name>/`：

```
codex/plugins/<name>/
├── .codex-plugin/plugin.json    # 插件元数据
└── skills/<skill>/SKILL.md      # 插件自带的技能
```

## 跨 agent 通用技能（`skills/`）

`skills/<name>/SKILL.md` 遵循 Agent Skills 规范，pi 由根清单加载；codex / opencode
可直接复用同一份内容（放入各自插件目录或引用）。新增技能只需在 `skills/` 建目录。

## MCP 服务（MCP-as-code）

MCP 的「代码 + 环境 + 密钥」不适合直接用 `mcp.json` 跨机同步（绝对路径、venv、cookie
都不通用），因此代码型的 MCP 采用：

1. 服务代码放 `mcp/<name>/`（随 pi 包安装到每台机器）；
2. `pi/extensions/<name>-mcp/` 扩展用 `pi.registerMcpServer()` 自动注册，路径相对包目录；
3. `skills/<name>-mcp/SKILL.md` 给 ai agent 的部署/排障说明（建环境、放 cookie）；
4. 秘密（cookie/token）只留在机器上，不进仓库；opencode 端同样用 `opencode.json`
   的 `{file:}` 引用（见 [`opencode/README.md`](opencode/README.md)）。

本地 MCP 服务统一用 `sh mcp/setup.sh <name>` 部署：建 venv、装依赖，并生成数据目录
启动器 `~/.local/share/token-lens-ex/mcp/<name>/run.sh`，供没有包内路径解析能力的
客户端（opencode）调用。

首个落地（均已迁移）：语雀、微博、QQ空间、ProcessOn、思源笔记 → 目录见
[`mcp/README.md`](mcp/README.md)，部署说明在各自的 `skills/<name>-mcp/SKILL.md`。
纯配置型（无本地代码、直连 URL）的 MCP 仍可放 `mcp.json`，由 TokenLens 基线同步。

## 发布新版本

1. 修改对应 agent 目录下的资源；
2. 更新根 `package.json` 的 `version`；
3. `git tag vX.Y.Z && git push origin vX.Y.Z`；
4. 各机器把安装 ref 指向新 tag（codex/opencode 同理）。
