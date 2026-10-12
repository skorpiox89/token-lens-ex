#!/usr/bin/env python3
"""ProcessOn 思维导图 -> 内嵌式 MarkMap（自包含 HTML 资源 + 思源 iframe 块）。

思源给 /assets/*.html 的响应带 `CSP: sandbox allow-scripts`（无 allow-same-origin），
外链脚本会被拦，所以 d3 + markmap-view 必须内联；为减小体积，节点树在 Python 侧
直接构建（不打包 900KB 的 markmap-lib，单文件约 340KB）。

配色对齐 ProcessOn 原图：
  背景 #393C41 / 根节点橙框 #FF8200 / 一级浅灰框 #E8EAEC / 子级白描边 / 连线 #E8EAEC

用法：
    make_markmap_html.py --chart <chartId> --doc <思源文档id> [--height 480] [--dry-run]
"""
import argparse
import json
import os
import random
import re
import string
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import processon_mind_to_markmap as pm  # noqa: E402
from xml.sax.saxutils import escape  # noqa: E402

SIYUAN = os.environ.get("SIYUAN_URL", "http://127.0.0.1:6806")
ACCESS_CODE = "11080703love!@#"
DEF_DIR = os.path.join(BASE, "export/archive/def")
VENDOR = os.path.join(BASE, "vendor/markmap")
ASSETS = "/root/code/si-yuan/workspace/data/assets"
ASSET_UID = 1000

# 与原图对应的节点样式
ROOT_CSS = (
    "background:#FF8200;color:#FFFFFF;padding:8px 18px;border-radius:10px;"
    "font-size:22px;font-weight:700;display:inline-block;"
)
L1_CSS = (
    "background:#E8EAEC;color:#404040;padding:4px 14px;border-radius:10px;"
    "font-size:16px;font-weight:600;display:inline-block;"
)
LN_CSS = (
    "border:1px solid #BCBFC1;color:#FFFFFF;padding:2px 10px;border-radius:10px;"
    "font-size:14px;display:inline-block;"
)

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  html, body { margin: 0; padding: 0; height: 100%; background: #393C41; overflow: hidden; }
  svg.markmap { width: 100%; height: 100%; }
  .markmap { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei",
             "Noto Sans CJK SC", "Source Han Sans SC", sans-serif; }
  .markmap-link { stroke: #E8EAEC !important; }
  .markmap-node > circle { stroke: #E8EAEC; fill: #393C41; }
  .markmap-node > line { display: none; }
</style>
</head>
<body>
<svg class="markmap"></svg>
<script>__D3__</script>
<script>__VIEW__</script>
<script>
var data = __DATA__;
var opts = markmap.deriveOptions({
  color: ['#E8EAEC'], colorFreezeLevel: 10, lineWidth: 2,
  initialExpandLevel: -1, maxWidth: __MAXW__,
  spacingHorizontal: 80, spacingVertical: 10, paddingX: 12
});
opts.autoFit = true; opts.zoom = false; opts.pan = false; opts.duration = 0;
var mm = markmap.Markmap.create('svg.markmap', opts, data);
function fit() { try { mm.fit(); } catch (e) {} }
setTimeout(fit, 60); setTimeout(fit, 300);
window.addEventListener('resize', fit);
</script>
</body>
</html>
"""


def login():
    req = urllib.request.Request(
        SIYUAN + "/api/system/loginAuth",
        data=json.dumps({"authCode": ACCESS_CODE}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return re.search(r"siyuan=([^;]+)", resp.headers.get("Set-Cookie", "")).group(1)


def post(path, payload, cookie):
    req = urllib.request.Request(
        SIYUAN + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Cookie": "siyuan=" + cookie},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def sql(stmt, cookie):
    res = post("/api/query/sql", {"stmt": stmt}, cookie)
    if res.get("code") != 0:
        raise RuntimeError(res.get("msg"))
    return res.get("data") or []


def _span(text, css):
    return f'<span style="{css}">{escape(str(text))}</span>'


def tree_to_data(node, depth=0):
    """ProcessOn 思维导图树 -> markmap 节点树（content 为带样式的 HTML）。"""
    title = pm._clean(node.get("title"))
    css = ROOT_CSS if depth == 0 else (L1_CSS if depth == 1 else LN_CSS)
    children = [tree_to_data(ch, depth + 1) for ch in (node.get("children") or [])]
    return {"content": _span(title, css), "children": children}


def count_nodes(data):
    return sum(1 + count_nodes(c) for c in data.get("children", []))


def build_html(title, data, max_width=360):
    def read(name):
        with open(os.path.join(VENDOR, name), encoding="utf-8") as fh:
            return fh.read()

    text = json.dumps(data, ensure_ascii=False)
    return (
        HTML.replace("__TITLE__", title)
        .replace("__DATA__", text)
        .replace("__MAXW__", str(max_width))
        .replace("__D3__", read("d3.min.js"))
        .replace("__VIEW__", read("markmap-view.js"))
    )


def find_def(chart_id):
    for f in os.listdir(DEF_DIR):
        if f.startswith(chart_id):
            return os.path.join(DEF_DIR, f)
    raise FileNotFoundError(chart_id)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chart", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--height", type=int)
    ap.add_argument("--max-width", type=int, default=360)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tree = pm.load_tree(find_def(args.chart))
    data = tree_to_data(tree)
    title = pm._clean(tree.get("title") or "MindMap")
    nodes = count_nodes(data)
    slug = re.sub(r'[\\/:*?"<>|#^\[\]\s]+', "_", title)[:40]
    stamp = time.strftime("%Y%m%d%H%M%S")
    fname = f"markmap-{slug}-{stamp}.html"
    height = args.height or (520 if nodes <= 40 else 640)
    html = build_html(title, data, args.max_width)
    print(f"节点 {nodes} 个，HTML {len(html)/1024:.0f} KB，高度 {height}px -> assets/{fname}")

    if args.dry_run:
        return

    os.makedirs(ASSETS, exist_ok=True)
    path = os.path.join(ASSETS, fname)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    os.chown(path, ASSET_UID, ASSET_UID)
    os.chmod(path, 0o644)

    cookie = login()
    block_id = stamp + "-" + "".join(random.choices(string.ascii_lowercase, k=7))
    prev = sql(
        f"SELECT id FROM blocks WHERE root_id='{args.doc}' AND type='b' ORDER BY sort LIMIT 1",
        cookie,
    )
    md = (
        f'<iframe frameborder="0" style="width:100%;height:{height}px;" '
        f'src="/assets/{fname}"></iframe>\n'
        f'{{: id="{block_id}" custom-data-assets="assets/{fname}" }}'
    )
    payload = {"dataType": "markdown", "data": md}
    if prev:
        payload["previousID"] = prev[0]["id"]
    else:
        payload["parentID"] = args.doc
    res = post("/api/block/insertBlock", payload, cookie)
    print("insert:", res.get("code"), res.get("msg"), "block:", block_id)


if __name__ == "__main__":
    main()
