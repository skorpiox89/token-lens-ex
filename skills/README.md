# skills

通用 Agent Skills 目录：每个技能一个子目录，内含 `SKILL.md`（Agent Skills 规范）：

```
skills/
└── my-skill/
    ├── SKILL.md
    └── scripts/…      # 可选：技能自带的脚本/资源
```

pi 通过根 `package.json` 的 `pi.skills` 加载这里的技能；opencode / codex 等
支持 Agent Skills 的 agent 也可以复用同一份内容。
