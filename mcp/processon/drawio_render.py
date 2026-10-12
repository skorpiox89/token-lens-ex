#!/usr/bin/env python3
"""用本机 drawio viewer 渲染 .drawio 为 PNG（QA 用）。

依赖 siyuan-drawio-plugin 的 webapp 目录（含 js/viewer-static.min.js）。
用 headless chromium 截图。用法：
    drawio_render.py out.png file1.drawio [file2.drawio ...]
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

WEBAPP = "/root/code/si-yuan/workspace/data/plugins/siyuan-drawio-plugin/webapp"
CHROME = "/root/.cache/ms-playwright/chromium_headless_shell-1187/chrome-linux/headless_shell"
PORT = 8899
HOST = "http://127.0.0.1:%d" % PORT

TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>drawio preview</title>
<style>html,body{margin:0;padding:0;background:#ffffff}</style></head>
<body>
<div class="mxgraph" style="max-width:100%%;" data-mxgraph="__CFG__"></div>
<script src="js/viewer-static.min.js"></script>
</body></html>"""


def start_server():
    try:
        import urllib.request

        urllib.request.urlopen(HOST + "/js/viewer-static.min.js", timeout=2)
        return None
    except Exception:
        pass
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=WEBAPP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    return proc


def render(drawio_path, png_path):
    xml = open(drawio_path, encoding="utf-8").read()
    model = re.search(r"<mxGraphModel[\s\S]*</mxGraphModel>", xml).group(0)
    mw = re.search(r'pageWidth="(\d+)"', xml)
    mh = re.search(r'pageHeight="(\d+)"', xml)
    pw, ph = int(mw.group(1)), int(mh.group(1))
    scale = min(1600 / pw, 1500 / ph, 1.6)
    win_w, win_h = max(400, int(pw * scale)), max(300, int(ph * scale))
    cfg = {"highlight": "#0000ff", "nav": False, "resize": True, "xml": model}
    html = TEMPLATE.replace("__CFG__", json.dumps(cfg, ensure_ascii=False).replace('"', "&quot;"))
    page = os.path.join(WEBAPP, "_preview_tmp.html")
    open(page, "w", encoding="utf-8").write(html)
    subprocess.run(
        [
            CHROME, "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
            "--window-size=%d,%d" % (win_w, win_h),
            "--timeout=12000", "--screenshot=" + png_path, HOST + "/_preview_tmp.html",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90,
    )
    os.remove(page)
    return os.path.exists(png_path) and os.path.getsize(png_path) > 500


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    proc = start_server()
    try:
        for f in sys.argv[2:]:
            name = os.path.splitext(os.path.basename(f))[0].split("_", 1)[-1]
            png = os.path.join(out, name + ".png")
            ok = render(f, png)
            print(("✓ " if ok else "✗ ") + png)
    finally:
        if proc:
            proc.send_signal(signal.SIGTERM)


if __name__ == "__main__":
    main()
