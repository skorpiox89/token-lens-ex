#!/usr/bin/env python3
"""检查微博 cookie 是否有效。

读取顺序：WEIBO_COOKIE 环境变量 → 本目录 cookie.txt → 数据目录 cookie.txt → ~/weibo-mcp/cookie.txt
退出码：0 = 有效；1 = 失效/出错。
"""
import json
import os
import sys
from pathlib import Path

CANDIDATES = [
    Path(__file__).resolve().parent / "cookie.txt",
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    / "token-lens-ex"
    / "mcp"
    / "weibo"
    / "cookie.txt",
    Path.home() / "weibo-mcp" / "cookie.txt",
]

cookie = (os.environ.get("WEIBO_COOKIE") or "").strip()
source = "WEIBO_COOKIE 环境变量"
if not cookie:
    for candidate in CANDIDATES:
        if candidate.is_file():
            cookie = candidate.read_text(encoding="utf-8").strip()
            source = str(candidate)
            break

if not cookie:
    sys.exit("未找到 cookie：可通过 WEIBO_COOKIE 环境变量或 cookie.txt 提供")

os.environ["WEIBO_COOKIE"] = cookie
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402


def fail(error):
    print(f"FAIL: {error}", file=sys.stderr)
    print("请重新登录 weibo.com，把请求头里的整段 Cookie 更新到 cookie.txt", file=sys.stderr)
    sys.exit(1)


try:
    me = json.loads(server.check_auth())
except Exception as error:  # noqa: BLE001
    fail(error)

print(
    f"OK: cookie 有效（来源 {source}），账号 {me['uid']} / {me.get('screen_name') or '?'}"
    f"（微博 {me.get('statuses_count')} 条，粉丝 {me.get('followers_count')}）"
)

try:
    page = json.loads(server.list_my_posts(page=1))
except Exception as error:  # noqa: BLE001
    fail(error)
print(f"第一页可读：{page['count']} 条（账号共约 {page['total']} 条）")
