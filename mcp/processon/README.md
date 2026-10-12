# processon-mcp

ProcessOn MCP Server（只读 · JWT 认证）。

把 ProcessOn「我的文件」里的图表读出来：目录树、图表定义（elements JSON）、
Mermaid / Markdown 大纲转换、批量导出 —— 便于把历史图表重新汇总到自建知识库（思源等）。

除「开启分享链接」外，不做任何写操作；不创建、不修改、不删除你的图表。

## 特性

- 📁 **目录树**：递归列出「我的文件」里的文件夹与图表（带 chartId）
- 🧾 **原始定义**：读回每张图的完整 elements JSON（`get_chart_def`）
- 🔁 **可编辑转换**：流程/架构类 → Mermaid flowchart；思维导图/大纲类 → Markdown 大纲
- 📦 **批量导出**：整目录导出 JSON + Markdown + index.md（`export_folder` / `export.py`）
- 🔗 **原图入口**：按需开启公开分享链接，便于在笔记里回链
- 🔐 账号密码可选：配置后 token 过期自动重登，省去手动换 token

## 快速开始

```bash
cd /root/processon-mcp
python3 -m venv venv
venv/bin/pip install "mcp>=1.2.0,<2"

# 凭证二选一（见下文）：
#   A. junkdrawer「认证获取」工具采集，写入 cookie.txt（推荐）
#   B. 手动从浏览器复制 token，写入 token.txt
chmod 600 cookie.txt token.txt 2>/dev/null

./check-auth.sh   # 自检登录态
```

### 获取凭证

**方式 A：认证获取工具（推荐）**

在 junkdrawer 的「工具 → 认证获取」里选择 **ProcessOn**，用真实浏览器登录后，
把生成的话术交给 AI，就会把 `token=<jwt>` 写入本目录的 `cookie.txt`。

**方式 B：手动复制**

1. 浏览器登录 <https://www.processon.com>
2. F12 → **Network** → 打开任意图表或刷新「我的文件」
3. 找任意 `/api/personal/...` 请求 → **Request Headers** → 复制 `token` 的值（形如 `eyJ...`）
4. 写入 `token.txt`（单行，也支持整段 `token=eyJ...` cookie）

### 可选：token 自动续期

把网页版登录手机号/密码（密码在本地 MD5 后传输）写进 `login.json`：

```json
{ "account": "13800000000", "password": "你的密码" }
```

或设置环境变量 `PROCESSON_ACCOUNT` / `PROCESSON_PASSWORD`。
配置后 token 过期会自动重登并刷新 `token.txt`；不配则过期后需手动更新。

## 工具一览

| 工具 | 用途 |
|------|------|
| `check_auth` | 检查 token / 显示账号与到期时间 |
| `list_files(folder_id, page, all_pages)` | 列某文件夹内容（JSON，含 id） |
| `list_tree(folder_id, max_depth)` | 递归目录树（Markdown，含 id） |
| `get_chart_def(chart_id, save)` | 读回完整 elements JSON + 元素统计 |
| `chart_to_markdown(chart_id, save)` | 转 Mermaid / Markdown 大纲 |
| `export_folder(folder_id, max_charts)` | 批量导出 JSON + Markdown + index.md |
| `export_chart_image(chart_id)` | [BETA] 尝试服务端导出高清图 |
| `share_chart(chart_id)` | 开启/复用公开分享链接（唯一写操作，幂等） |

## 命令行批量导出

```bash
./venv/bin/python export.py --max 500 --out export/siyuan
# → export/siyuan/{def,md}/ 和 index.md
```

## 转 draw.io（.drawio）

流程/架构图想保留原版式时，可在 Mermaid 之外再转一份 draw.io 文件：

```bash
./venv/bin/python processon_to_drawio.py export/def/<chartId>.json -o /tmp/chart.drawio --name "图名"
```

- 保留元素绝对坐标、大小、文案、连线折点；容器（如「集群」框）成为子图形
- 样式按 ProcessOn 默认主题还原：白底黑框圆角矩形、黄色便笺（右上折角）、
  黑色细箭头 + 白底标签；曲线连线用 `curved=1` 近似
- 思源里想「插入式」显示：把 .drawio 放到
  `workspace/data/storage/petal/siyuan-drawio-plugin/`，再用「思源Draw.io插件」
  在文档中插入 iframe 块（src 指向 `/plugins/siyuan-drawio-plugin/webapp/?...#U<路径>`，
  IAL 带 `custom-data-assets`）
- 也可把 .drawio 导出目录留档到 `export/drawio/`（已有 `62f617b3f346fb0731874954.drawio` 即
  `ops-job-supervisor` 一图）

## 思维导图 → 思源 MarkMap（markmap 视图插件）

```bash
./venv/bin/python processon_mind_to_markmap.py export/archive/def/<chartId>.json -o out.md --url <原图链接>
# 上面只生成 markdown；写进思源并套用原生样式：
./venv/bin/python apply_markmap_spans.py --chart <chartId> --doc <思源文档id> --url <原图链接>
```

要点（踩过的坑）：

- 思源 markmap 插件渲染的是**整篇文档**：文档开头用单行 flow 格式写配置，
  `markmap: {color: ["#9A9A9A"], colorFreezeLevel: 4, lineWidth: [1, 0, 1], initialExpandLevel: -1, maxWidth: 320}`
  （插件把 frontmatter 换行换成空格后做 YAML 解析，所以不能写多行块格式）
- 这三行配置块（两条 `---` + 配置行）在正文里用块属性 `style="display:none"` **隐藏**：
  IAL 不会进导出的 markdown，所以插件照常读到配置，而文档看起来干净
- 插件会把根节点文字强制换成**文档标题**（无法自定义样式）
- 节点样式用**思源原生行内 span**（`data-type="text"` + 自定义 CSS）：
  正文能正常渲染，导出 markdown 时也保持 `<span style=...>`，markmap 同样能识别
- 形如 `1. xxx` 的节点标题在中间大纲里要写作 `1\. xxx`，否则会被当成有序列表标记
- 可配置项白名单：color / colorFreezeLevel / lineWidth / duration / fitRatio /
  initialExpandLevel / maxInitialScale / maxWidth / nodeMinHeight / paddingX /
  spacingHorizontal / spacingVertical / zoom / pan
- 限制：markmap 布局左右对称展开（原图是单侧）；背景跟随思源主题，无法单独指定深色

### 正文内嵌版（推荐）：make_markmap_html.py

markmap 插件只在弹窗里显示（Ctrl+Alt+M），正文里看不到图；如需正文内嵌：

```bash
./venv/bin/python make_markmap_html.py --chart <chartId> --doc <思源文档id> [--height 430]
```

- 生成**自包含 HTML**（内联 d3 + markmap-view，颜色对齐 ProcessOn：背景 #393C41、
  橙色根节点 #FF8200、浅灰一级框 #E8EAEC、白描边子节点、白线），存到 `data/assets/`，
  再在文档里插 iframe 块
- ⚠️ 思源给 `/assets/*.html` 的响应带 `CSP: sandbox allow-scripts`（无 allow-same-origin）：
  **外链脚本加载不了、也不发 cookie**，所以库必须内联；为了减小体积，节点树在 Python 侧
  直接构建（不打包 900KB 的 markmap-lib，单文件约 330KB）
- 节点树格式就是 markmap 的 `{content, children}`，视图层 `Markmap.create(svg, opts, tree)`
  不需要 markmap-lib

## 接入 pi（mcp.json）

```json
"processon": {
  "command": "/root/processon-mcp/venv/bin/python",
  "args": ["/root/processon-mcp/server.py"],
  "env": { "PROCESSON_COOKIE": "!cat /root/processon-mcp/cookie.txt" },
  "exposure": "deferred",
  "description": "ProcessOn（只读：目录树/图表定义/Mermaid 转换/批量导出）"
}
```

## 接口备注（网页端私有 API，逆向所得）

| 用途 | 请求 |
|------|------|
| 登录 | `POST /api/personal/login/v2/account`（密码 MD5）→ `data.token` |
| 我是谁 | `GET /api/personal/user/info` |
| 列文件 | `GET /api/personal/folder/load_files?folderId=&pageSize=&page=` |
| defId | `GET /api/personal/canvas/get/chartdefids?chartId=` |
| 图定义 | `GET /api/personal/diagraming/get/chart/def?chartId=&defId=` |
| 导出 | `GET /api/personal/chart/export/get/user/power?chartId=&exportType=jpghd` |
| 分享 | `GET /api/personal/chart/share/open?chartId=` |

鉴权失效时返回 `{"code":"408","msg":"鉴权失败"}`；服务端会据此自动重登（若配置了账号密码）。

## 已知限制

- `export_chart_image` 的导出管线未经真实账号验证（BETA）：若接口是异步任务，会把原始返回存 `export/diag/`，按返回结构再适配
- `load_files` 每页数量由服务端决定，超大目录请用 `all_pages=true`
- Mermaid 转换基于坐标/连线启发式，转换结果会带 `warnings`，重要图请对照原图
- ProcessOn 是私有接口，接口变动会导致失效；失效时先跑 `./check-auth.sh` 定位
