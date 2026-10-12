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
├── pi/                          # pi 专用
│   ├── extensions/              # pi 扩展：每个子目录一个，入口 index.ts
│   │   └── pi-token-lens-ttft/
│   └── skills/                  # pi 专用技能
├── codex/                       # Codex 专用
│   └── plugins/                 # Codex 插件：每个子目录一个，含 .codex-plugin/plugin.json
└── opencode/                    # opencode 专用
    └── plugins/                 # opencode 插件
```

## 各家 agent 的接入方式

| agent | 安装/发现方式 | 资源放哪 |
|---|---|---|
| **pi** | `pi install git:github.com/skorpiox89/token-lens-ex@vX.Y.Z`（读根 `package.json` 的 `pi` 字段） | `pi/extensions/*/index.ts`、`pi/skills/`、根 `skills/` |
| **codex** | `codex plugin marketplace add skorpiox89/token-lens-ex@vX.Y.Z` + `codex plugin add <name>`（读根 `.agents/plugins/marketplace.json`） | `codex/plugins/<name>/`（其中 skills 放插件的 `skills/` 下） |
| **opencode** | `opencode plugin add github:skorpiox89/token-lens-ex`（npm/git 包以仓库根为单位） | `opencode/plugins/<name>/`，由 `opencode/index.ts` 统一 re-export（每个插件在子目录导出） |
| 其他 | 按各自规范，新增顶层目录（如 `cline/`）并在对应清单里注册 | — |

### pi

```bash
pi install git:github.com/skorpiox89/token-lens-ex@v0.2.0   # 固定 tag，推荐
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

## 发布新版本

1. 修改对应 agent 目录下的资源；
2. 更新根 `package.json` 的 `version`；
3. `git tag vX.Y.Z && git push origin vX.Y.Z`；
4. 各机器把安装 ref 指向新 tag（codex/opencode 同理）。
