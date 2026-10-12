# opencode 资源（预留）

opencode 的 `plugin add` 以 **npm/git 包（仓库根）** 为单位安装，不支持 monorepo
子目录直接安装。因此约定：

- 插件代码放 `opencode/plugins/<name>/`，每个插件导出 opencode plugin；
- 仓库根的 `opencode/index.ts` 统一 re-export 所有插件（未来加），
  根 `package.json` 的入口指向它；
- 安装：`opencode plugin add github:skorpiox89/token-lens-ex`，或把子目录作为
  独立 npm 包发布后 `opencode plugin add <npm 包名>`。

本地开发也可以直接把插件文件软链到 `~/.config/opencode/plugin/`。

说明：目前尚未放入 opencode 插件，先预留目录。
