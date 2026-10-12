# yuque MCP（语雀本地 stdio 服务）

把语雀知识库读写封装成 MCP 工具（本地 Cookie 模式，无需会员）。
本目录是**服务代码**；在 pi 里通过 `pi/extensions/yuque-mcp/` 扩展自动注册，
不依赖 `mcp.json`。环境与 cookie 的处理见下面。

## 组件

| 文件 | 作用 |
|---|---|
| `server.py` | MCP stdio 服务（`mcp>=1.2.0,<2`） |
| `requirements.txt` | Python 依赖 |
| `setup.sh` | 在 `~/.local/share/token-lens-ex/mcp/yuque/venv` 建独立 venv（不放进包目录，避免 pi 更新时被清） |
| `check_cookie.py` | 校验 cookie 是否有效 |
| `test_client.py` | 协议级自测（stdio 握手 + tools/list） |

## 环境与凭据

```bash
./setup.sh                              # 建 venv + 装依赖
cp cookie.txt ~/.local/share/token-lens-ex/mcp/yuque/cookie.txt   # 放 cookie（勿提交）
python3 check_cookie.py                 # 验证
```

cookie 获取：浏览器 F12 → Network → 刷新语雀 → 任意请求的 Request Headers 里整段复制
`Cookie:` 的值；有效期约 2 周。也支持官方令牌 `YUQUE_TOKEN`（需超级会员）。

扩展注册时的查找顺序：

1. `YUQUE_COOKIE` 环境变量
2. `~/.local/share/token-lens-ex/mcp/yuque/cookie.txt`（推荐）
3. `~/yuque-mcp/cookie.txt`（兼容旧路径）
4. `YUQUE_TOKEN` 环境变量（走官方 API，优先于 cookie）

运行环境优先用数据目录里的 venv；没有 venv 时若系统有 `uv`，回退到
`uv run --with 'mcp>=1.2.0,<2' server.py`（首次联网拉依赖）。

## 手动运行（调试用）

```bash
V=~/.local/share/token-lens-ex/mcp/yuque/venv
YUQUE_COOKIE="$(cat ~/.local/share/token-lens-ex/mcp/yuque/cookie.txt)" "$V/bin/python" server.py
```
