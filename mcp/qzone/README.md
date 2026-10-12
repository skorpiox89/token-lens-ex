# qzone-mcp（本地只读版）

仓库：https://github.com/skorpiox89/qzone-mcp

QQ空间 MCP Server（stdio，基于 FastMCP）。**纯 Cookie 认证，只读**：说说、日志（文章）、相册/相片，不做任何写操作（不发说说、不评论、不删除）。

接口路径、请求参数与 `g_tk` 算法移植自 [ShunCai/QZoneExport](https://github.com/ShunCai/QZoneExport)（MIT License）。

## 工具清单（7 个，全部只读）

| 工具 | 说明 | 主要参数 |
|---|---|---|
| `check_auth` | 验证 cookie，返回空间主人资料 | 无 |
| `list_shuoshuo` | 说说列表（时间倒序） | `pos`、`num`（≤40） |
| `get_shuoshuo` | 单条说说全文 + 评论 + 图片 | `tid` |
| `list_blogs` | 日志（文章）列表 | `pos`、`num`（≤40） |
| `get_blog` | 单篇日志完整内容 | `blogid`、`format`（text/html） |
| `list_albums` | 相册列表 | `pos`、`num`（≤50） |
| `list_photos` | 相册内相片（原图/高清/普通图地址） | `album_id`、`pos`、`num`（≤60） |

## Cookie 获取

1. 浏览器登录 <https://user.qzone.qq.com>
2. F12 → Network → 刷新页面 → 点击任意请求
3. 复制 Request Headers 里整行 `cookie:` 的值（很长，必须包含 `uin` 和 `p_skey`）

## 部署

```bash
python3 -m venv venv
./venv/bin/pip install "mcp>=1.2.0,<2"
printf '%s' '粘贴整段cookie' > cookie.txt && chmod 600 cookie.txt
./check-cookie.sh
```

MCP 客户端配置（pi 示例，`~/.pi/agent/mcp.json`）：

```json
{
  "mcpServers": {
    "qzone": {
      "command": "/root/qzone-mcp/venv/bin/python",
      "args": ["/root/qzone-mcp/server.py"],
      "env": { "QZONE_COOKIE": "!cat /root/qzone-mcp/cookie.txt" },
      "description": "QQ空间（只读：说说/日志/相册）",
      "exposure": "deferred"
    }
  }
}
```

## 已知限制与注意事项

- **风控**：QQ空间对高频请求敏感。分页时请控制频率和页大小，连续大量拉取可能触发验证或临时限制。
- **Cookie 过期**：约数周失效（取决于登录态），过期后所有调用失败，重走"Cookie 获取"流程即可。
- **qzonetoken**：从空间首页 HTML 动态提取，缓存 30 分钟。
- **日志正文**：接口返回 GBK 编码的 HTML，`get_blog` 默认转纯文本，可传 `format=html` 拿原始 HTML。
- **相册分页**：`pos`/`num` 对应接口的 `pageStart`/`pageNum`。
- 导出的数据属于个人隐私，注意存放位置，不要提交到公开仓库。
- 仅供导出/备份自己的空间数据使用，请遵守腾讯的服务条款。

## 文件

| 文件 | 说明 |
|---|---|
| `server.py` | MCP server 本体（只读工具） |
| `cookie.txt` | qzone 登录态，**不进 git**，权限 600 |
| `check-cookie.sh` | cookie 有效性检查 |
