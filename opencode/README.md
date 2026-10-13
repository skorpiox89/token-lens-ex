# opencode 资源

opencode 与 pi 不同：没有「包内资源自动注册」，本地 MCP 走 `opencode.json` 的
`mcp.servers`。为了让这份配置能被 TokenLens 基线安全地跨机同步，约定如下：

- **配置里零明文**：cookie / token / API key 全部放机器本地文件，配置用 opencode 的
  `{file:...}` 引用（opencode 支持 `{file:...}` 与 `{env:...}` 插值）。
- **配置里零本机绝对路径**：本机路径用 `{env:HOME}/...` 前缀；本地 MCP 服务统一通过
  数据目录里的启动器 `~/.local/share/token-lens-ex/mcp/<name>/run.sh` 调用
  （由 `sh mcp/setup.sh <name>` 生成，内含该机器自己的 venv/仓库路径）。
- 这样 capture 到 TokenLens 的 `opencode.json` 不含任何秘密与机器路径；换机 apply 后
  只需补齐本地秘密文件即可。

## 配置片段

```jsonc
{
  "mcp": {
    "servers": {
      "weibo": {
        "type": "local",
        "command": ["{env:HOME}/.local/share/token-lens-ex/mcp/weibo/run.sh"],
        "environment": {
          "WEIBO_COOKIE": "{file:~/.local/share/token-lens-ex/mcp/weibo/cookie.txt}"
        }
      },
      "siyuan": {
        "type": "remote",
        "url": "http://127.0.0.1:6806/mcp",
        "oauth": false,
        "headers": {
          "Authorization": "Token {file:~/.local/share/token-lens-ex/mcp/siyuan/token.txt}"
        }
      }
    }
  },
  "provider": {
    "opencode-go": {
      "options": {
        "apiKey": "{file:~/.local/share/token-lens-ex/opencode/keys/opencode-go.txt}"
      }
    }
  }
}
```

秘密文件位置（机器本地，永不进仓库、永不进 TokenLens 基线）：

| 用途 | 路径 |
|---|---|
| MCP cookie / token | `~/.local/share/token-lens-ex/mcp/<name>/cookie.txt` / `token.txt` |
| provider API key | `~/.local/share/token-lens-ex/opencode/keys/<providerID>.txt` |

## TokenLens 同步范围（AI Agent 配置同步）

相对配置目录（`~/.config/opencode`）：

| 受管 | 类型 | 说明 |
|---|---|---|
| `opencode.json` / `opencode.jsonc` / `cli.json` | 文件 | 配置（MCP、provider、TUI） |
| `AGENTS.md` | 文件 | 全局指令 |
| `skills/**` | 目录 | 技能（opencode 扫描 `skill/` 与 `skills/`，本约定用 `skills/`） |
| `plugin/**` | 目录 | 本地插件（opencode 扫描 `plugin/` 与 `plugins/`，本约定用 `plugin/`） |

仍不同步：`service.json`（密码/env）、`auth.json`、`node_modules/`、`package.json`/
`bun.lock`。`opencode plugin add` 安装的 npm/git 插件只随 `opencode.json` 同步声明，
目标机需自行 `opencode plugin add <pkg>` 补齐依赖（依赖清单同步属于 P2）。

## 新机部署顺序

1. 拿到仓库（`git clone`，或 pi 包的 `~/.pi/agent/git/github.com/skorpiox89/token-lens-ex`）；
2. `sh mcp/setup.sh <name>`：建 venv、装依赖、生成 `run.sh`；
3. 放秘密文件（`cookie.txt` / `token.txt` / `keys/<providerID>.txt`）；
4. 再同步 / apply `opencode.json`；
5. 验证：`opencode debug config`（配置能解析）、`opencode mcp list`（server 全部 connected）。

> 顺序很重要：`{file:}` 指向的文件必须存在，否则整份 `opencode.json` 判为无效，
> 不是只坏一个 server。

## 注意事项

- 秘密文件不要带换行（用 `printf` 写入），`{file:}` 不会 trim；
- `command` 数组里不能直接写 `~/...`（opencode 不展开裸 `~`），必须 `{env:HOME}/...`；
- `{file:}` 支持写在字符串中间（如 `"Token {file:...}"`），也支持绝对路径 / `~/` 前缀；
- Windows 需把 `run.sh` 换成 `.cmd`、`{env:HOME}` 换成 `{env:USERPROFILE}`，目前未提供；
- 插件目录 `plugins/` 仍为预留：opencode 的 `plugin add` 以仓库根 npm/git 包为单位，
  需要时在根 `package.json` 增加入口并在此目录按 `plugins/<name>/` 放置。
