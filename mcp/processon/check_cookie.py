#!/usr/bin/env python3
"""检查 ProcessOn cookie 是否有效。

读取顺序：PROCESSON_COOKIE 环境变量 → 本目录 cookie.txt → 数据目录 cookie.txt → ~/processon-mcp/cookie.txt
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
    / "processon"
    / "cookie.txt",
    Path.home() / "processon-mcp" / "cookie.txt",
]

cookie = (os.environ.get("PROCESSON_COOKIE") or "").strip()
source = "PROCESSON_COOKIE 环境变量"
if not cookie:
    for candidate in CANDIDATES:
        if candidate.is_file():
            cookie = candidate.read_text(encoding="utf-8").strip()
            source = str(candidate)
            break

if not cookie:
    sys.exit("未找到 cookie：可通过 PROCESSON_COOKIE 环境变量或 cookie.txt 提供")

os.environ["PROCESSON_COOKIE"] = cookie
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402


def fail(error):
    print(f"FAIL: {error}", file=sys.stderr)
    print("请重新登录 processon.com，更新 cookie.txt 后重试", file=sys.stderr)
    sys.exit(1)


try:
    me = json.loads(server.check_auth())
except Exception as error:  # noqa: BLE001
    fail(error)
if not me.get("ok"):
    fail(me.get("error"))

print(
    f"OK: cookie 有效（来源 {source}），账号 {me.get('nickName') or '?'} "
    f"(userId={me.get('userId')})，剩余 {me.get('daysLeft')} 天"
)

try:
    listing = json.loads(server.list_files(page=1, page_size=5))
except Exception as error:  # noqa: BLE001
    fail(error)
if not listing.get("ok"):
    fail(listing.get("error"))
print(f"顶层可读：{listing['count']['folders']} 个文件夹 / {listing['count']['charts']} 张图（本页）")
