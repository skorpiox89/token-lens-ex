#!/usr/bin/env python3
"""检查 QQ空间 cookie 是否有效。

读取顺序：QZONE_COOKIE 环境变量 → 本目录 cookie.txt → 数据目录 cookie.txt → ~/qzone-mcp/cookie.txt
退出码：0 = 有效；1 = 失效/出错。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CANDIDATES = [
    Path(__file__).resolve().parent / "cookie.txt",
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    / "token-lens-ex"
    / "mcp"
    / "qzone"
    / "cookie.txt",
    Path.home() / "qzone-mcp" / "cookie.txt",
]

cookie = (os.environ.get("QZONE_COOKIE") or "").strip()
source = "QZONE_COOKIE 环境变量"
if not cookie:
    for candidate in CANDIDATES:
        if candidate.is_file():
            cookie = candidate.read_text(encoding="utf-8").strip()
            source = str(candidate)
            break

if not cookie:
    sys.exit("未找到 cookie：可通过 QZONE_COOKIE 环境变量或 cookie.txt 提供")

cookies = {}
for part in cookie.split(";"):
    part = part.strip()
    if "=" in part:
        key, value = part.split("=", 1)
        cookies[key] = value

raw_uin = cookies.get("uin") or cookies.get("p_uin") or ""
match = re.search(r"\d+", raw_uin)
if not match:
    sys.exit("cookie 中没有 uin")
uin = match.group(0)

skey = cookies.get("p_skey") or cookies.get("skey") or cookies.get("rv2") or ""
if not skey:
    sys.exit("cookie 中没有 p_skey/skey，无法计算 g_tk")
g_tk = 5381
for char in skey:
    g_tk = (g_tk + (g_tk << 5) + ord(char)) & 0xFFFFFFFF
g_tk &= 0x7FFFFFFF

url = (
    "https://user.qzone.qq.com/proxy/domain/base.qzone.qq.com/cgi-bin/user/cgi_userinfo_get_all"
    + "?"
    + urllib.parse.urlencode({"uin": uin, "vuin": uin, "fupdate": 1, "rd": 0.5, "g_tk": g_tk})
)
request = urllib.request.Request(
    url,
    headers={
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://user.qzone.qq.com/{uin}",
    },
)
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        text = response.read().decode("utf-8", errors="replace").strip()
    wrapped = re.match(r"^[A-Za-z_][\w.]*\s*\(([\s\S]*)\)\s*;?\s*$", text)
    payload = json.loads(wrapped.group(1) if wrapped else text)
    data = payload.get("data") or payload
    if payload.get("code") not in (0, None) or not data:
        sys.exit(f"FAIL: QQ空间返回异常：{text[:200]}")
    print(f"OK: cookie 有效（来源 {source}），账号 {uin} / {data.get('nickname') or data.get('name') or '?'}")
except urllib.error.HTTPError as error:
    sys.exit(f"FAIL: HTTP {error.code} —— cookie 可能已过期，请重新复制到 cookie.txt")
except Exception as error:  # noqa: BLE001
    sys.exit(f"FAIL: {error}")
