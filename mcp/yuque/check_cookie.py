#!/usr/bin/env python3
"""检查语雀 cookie 是否有效（yalogin 态）。

读取顺序：YUQUE_COOKIE 环境变量 → ./cookie.txt → 数据目录 cookie.txt → ~/yuque-mcp/cookie.txt
退出码：0 = 有效；1 = 失效或出错。
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CANDIDATES = [
    Path(__file__).resolve().parent / "cookie.txt",
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "token-lens-ex" / "mcp" / "yuque" / "cookie.txt",
    Path.home() / "yuque-mcp" / "cookie.txt",
]

cookie = (os.environ.get("YUQUE_COOKIE") or "").strip()
source = "YUQUE_COOKIE 环境变量"
if not cookie:
    for candidate in CANDIDATES:
        if candidate.is_file():
            cookie = candidate.read_text(encoding="utf-8").strip()
            source = str(candidate)
            break

if not cookie:
    sys.exit("未找到 cookie：可通过 YUQUE_COOKIE 环境变量或 cookie.txt 提供")

request = urllib.request.Request(
    "https://www.yuque.com/api/mine",
    headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0", "Referer": "https://www.yuque.com/"},
)
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
except urllib.error.HTTPError as error:
    sys.exit(f"cookie 失效（HTTP {error.code}，来源 {source}）：请重新复制浏览器 cookie")
except Exception as error:  # noqa: BLE001
    sys.exit(f"检查失败（来源 {source}）：{error}")

user = (payload.get("data") or {}).get("name") or (payload.get("data") or {}).get("login")
print(f"cookie 有效（来源 {source}）：{user}")
