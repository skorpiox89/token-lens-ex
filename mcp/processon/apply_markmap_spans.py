#!/usr/bin/env python3
"""把 ProcessOn 思维导图写进思源文档，并做成 MarkMap 可用的原生行内样式。

步骤：
  1. 用「纯文本大纲 + frontmatter」覆盖文档内容（frontmatter 供 markmap 插件读取配置）
  2. 查出各列表项段落，按层级替换为「思源原生 span + ProcessOn 样式」
     （原生 span 正文能正常渲染，导出 markdown 时又是 <span style=...>，markmap 也能用）

用法：
    apply_markmap_spans.py --chart <chartId> --doc <docId> [--url <原图链接>]
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

SIYUAN = os.environ.get("SIYUAN_URL", "http://127.0.0.1:6806")
ACCESS_CODE = "11080703love!@#"
DEF_DIR = os.path.join(BASE, "export/archive/def")

# 与 ProcessOn 原图对应的节点样式（思源浅色主题下的等价做法）
L1_CSS = (
    "background-color:#E9E9E9;border:1px solid #E9E9E9;border-radius:9px;"
    "padding:2px 10px;font-weight:600;font-size:15px;"
)
LN_CSS = (
    "border:1px solid #A6A6A6;border-radius:9px;padding:1px 8px;"
    "color:#333333;font-size:13px;"
)


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


def plain_outline(tree, source_url):
    """不带样式的纯文本大纲（先建结构用）。"""
    lines = []
    depths = {}

    def walk(node, depth):
        title = pm._clean(node.get("title"))
        if depth > 0 and title:
            # 形如 “1. xxx” 的标题会被 markdown 当成有序列表标记，转义句点
            text = re.sub(r"^(\d+)\.\s", r"\1\\. ", title)
            lines.append("  " * (depth - 1) + "- " + text)
            depths[title] = depth
        for ch in node.get("children") or []:
            walk(ch, depth + 1)

    walk(tree, 0)
    opts = pm.OPTS
    head = ["---", f"markmap: {{{opts}}}", "---", ""]
    if source_url:
        head += [f"> 来源：[ProcessOn 原图]({source_url}) · 归档于 2026-10-10", ""]
    return "\n".join(head + lines) + "\n", depths


def find_def(chart_id):
    for f in os.listdir(DEF_DIR):
        if f.startswith(chart_id):
            return os.path.join(DEF_DIR, f)
    raise FileNotFoundError(chart_id)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chart", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--url")
    args = ap.parse_args()

    tree = pm.load_tree(find_def(args.chart))
    md, depths = plain_outline(tree, args.url)
    cookie = login()

    # 1) 覆盖文档：纯文本大纲 + frontmatter
    res = post("/api/block/updateBlock", {"id": args.doc, "dataType": "markdown", "data": md}, cookie)
    if res.get("code") != 0:
        raise SystemExit("更新文档失败: " + str(res.get("msg")))
    print(f"1) 已写入大纲（{len(depths)} 个节点）")

    # 2) 等索引，查列表项段落（内容匹配上才算就绪）
    rows = []
    for _ in range(15):
        rows = sql(
            f"SELECT p.id pid, p.content FROM blocks p JOIN blocks i ON p.parent_id=i.id "
            f"WHERE i.root_id='{args.doc}' AND i.type='i' AND p.type='p'",
            cookie,
        )
        got = {(r["content"] or "").strip() for r in rows}
        if got == set(depths):
            break
        time.sleep(0.8)
    print(f"2) 查到列表项段落 {len(rows)} / {len(depths)}")

    # 3) 逐条替换为原生 span
    done = 0
    for r in rows:
        text = (r["content"] or "").strip()
        depth = depths.get(text)
        if depth is None:
            print("   ? 未匹配:", text[:30])
            continue
        css = L1_CSS if depth == 1 else LN_CSS
        dom = (
            f'<div data-node-id="{r["pid"]}" data-type="NodeParagraph" class="p">'
            f'<div contenteditable="true" spellcheck="false">'
            f'<span data-type="text" style="{css}">{text}</span>'
            f'</div><div class="protyle-attr" contenteditable="false">\u200b</div></div>'
        )
        rr = post("/api/block/updateBlock", {"id": r["pid"], "dataType": "dom", "data": dom}, cookie)
        if rr.get("code") == 0:
            done += 1
        else:
            print("   ✗ 替换失败:", text[:30], rr.get("msg"))
    print(f"3) 已套用样式 {done} 个节点")

    # 4) 把 frontmatter 的 3 个块在正文里隐藏（导出 markdown 不受影响，插件照常读到配置）
    hide = sql(
        f"SELECT id FROM blocks WHERE root_id='{args.doc}' AND "
        "((type='tb' AND markdown='---') OR (type='p' AND markdown LIKE 'markmap:%'))",
        cookie,
    )
    hidden = 0
    for h in hide:
        if post("/api/attr/setBlockAttrs", {"id": h["id"], "attrs": {"style": "display:none"}}, cookie).get("code") == 0:
            hidden += 1
    print(f"4) 已隐藏 frontmatter 块 {hidden} 个（正文不可见，插件仍读取）")


if __name__ == "__main__":
    main()
