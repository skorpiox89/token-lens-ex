# Codex 资源（预留）

Codex 插件放 `plugins/<name>/`，每个插件包含：

```
codex/plugins/<name>/
├── .codex-plugin/plugin.json    # 插件元数据（name/version/description 等）
└── skills/<skill>/SKILL.md      # 插件自带技能（Agent Skills 规范）
```

插件需要在仓库根的 `.agents/plugins/marketplace.json` 里注册：

```json
{
  "name": "token-lens-ex",
  "interface": { "displayName": "TokenLens Ex" },
  "plugins": [
    {
      "name": "<name>",
      "source": { "source": "local", "path": "./codex/plugins/<name>" },
      "policy": { "installation": "AVAILABLE" },
      "category": "Productivity"
    }
  ]
}
```

安装（在 codex 里）：

```bash
codex plugin marketplace add skorpiox89/token-lens-ex@vX.Y.Z
codex plugin add <name>
```

说明：目前尚未放入 codex 插件，`marketplace.json` 暂留空清单（`plugins: []`），
第一个插件落地时再注册。
