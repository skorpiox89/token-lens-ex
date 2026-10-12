#!/usr/bin/env python3
"""ProcessOn 思维导图（mind_free/mind_org）→ MarkMap 文档 markdown。

还原 ProcessOn 的节点样式（思源浅色主题下的等价做法）：
  - 一级节点：浅灰圆角底色 + 深色粗体（原图为浅色框）
  - 二三级节点：细描边圆角 + 深色文字（原图为白色描边框）
  - 连线：单色灰（原图为浅白曲线）
根节点由 SiYuan markmap 插件用文档标题渲染，无法加样式。

用法：
    processon_mind_to_markmap.py <def.json> [-o out.md] [--url 原图链接]
"""
import argparse
import json
import re

# 一级节点样式（对应原图浅色圆角框）
L1_STYLE = (
    "background:#E9E9E9;color:#111111;padding:3px 12px;border-radius:9px;"
    "font-weight:600;font-size:15px;"
)
# 二三级节点样式（对应原图白色描边框）
LN_STYLE = (
    "border:1px solid #969696;color:#333333;padding:1px 9px;border-radius:9px;"
    "font-size:13px;"
)
OPTS = (
    'color: ["#9A9A9A"], colorFreezeLevel: 4, lineWidth: [1, 0, 1], '
    "initialExpandLevel: -1, maxWidth: 320, spacingHorizontal: 70, "
    "spacingVertical: 8, paddingX: 10"
)


def _clean(t):
    t = str(t or "").strip().replace("\n", " ")
    return re.sub(r"\s+", " ", t)


def render(tree, source_url):
    lines = []

    def walk(node, depth):
        title = _clean(node.get("title"))
        if depth > 0 and title:
            indent = "  " * (depth - 1)
            style = L1_STYLE if depth == 1 else LN_STYLE
            lines.append(f'{indent}- <span style="{style}">{title}</span>')
        for ch in node.get("children") or []:
            walk(ch, depth + 1)

    walk(tree, 0)
    head = [f"---", f"markmap: {{{OPTS}}}", "---", ""]
    if source_url:
        head += [f"> 来源：[ProcessOn 原图]({source_url}) · 归档于 2026-10-10", ""]
    return "\n".join(head + lines) + "\n"


def load_tree(path):
    data = json.load(open(path, encoding="utf-8"))
    defr = data["def"] if "def" in data else data
    return json.loads(defr) if isinstance(defr, str) else defr


def main():
    ap = argparse.ArgumentParser(description="ProcessOn mind -> MarkMap markdown")
    ap.add_argument("def_json")
    ap.add_argument("-o", "--output")
    ap.add_argument("--url")
    args = ap.parse_args()
    tree = load_tree(args.def_json)
    md = render(tree, args.url)
    out = args.output or (args.def_json.rsplit(".", 1)[0] + ".markmap.md")
    open(out, "w", encoding="utf-8").write(md)
    n = len(re.findall(r"^\s*- ", md, re.M))
    print(f"✓ {out}  （{n} 个节点）")


if __name__ == "__main__":
    main()
