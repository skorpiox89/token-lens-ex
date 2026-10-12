#!/usr/bin/env python3
"""ProcessOn 图表定义（def JSON）-> draw.io（mxfile）转换。

把 `server._chart_def_raw()` 导出的 def（elements: rectangle/roundRectangle/round/
text/standardText/note/linker 等）转换成 draw.io 可编辑的 .drawio 文件，尽量保留：

  - 元素绝对坐标、大小、旋转、层级；容器（分组框）成为子图形
  - 连线两端绑定的元素（source/target）与折点（points），
    curve 用 curved=1，normal/broken 用直线段
  - ProcessOn 样式：填充色/描边色/线宽/虚实线、起止箭头（solidArrow）、
    字体大小/粗斜体/颜色/对齐、透明度
  - 默认主题：白底黑框圆角矩形、圆形=ellipse、黄色便笺（右上折角）

用法：
    processon_to_drawio.py <def.json> [-o out.drawio] [--name 图名]
def.json 可以是 `{"def": "<json string>"}`（get_chart_def 的落盘格式），
也可以是直接的 def 对象。
"""

import argparse
import base64
import json
import mimetypes
import os
import random
import re
import string
import time
import urllib.parse
from xml.sax.saxutils import escape, quoteattr

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "export/drawio/assets")


def image_data_uri(file_id):
    """把 ProcessOn 素材（fileId 形如 /images/...）缓存的本地文件转成 drawio 可用的 data URI。

    注意：drawio 样式串以 ";" 分隔，所以不能用标准的 "...;base64," 写法：
      - 位图：data:image/png,<base64>（drawio 渲染时自动补 ;base64）
      - SVG：data:image/svg+xml,<百分号编码的 SVG>
    """
    if not file_id:
        return None
    path = os.path.join(ASSET_DIR, str(file_id).lstrip("/"))
    if not os.path.exists(path):
        return None
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as fh:
        data = fh.read()
    if mime == "image/svg+xml":
        return "data:image/svg+xml," + urllib.parse.quote(data.decode("utf-8", "replace"), safe="")
    return "data:%s,%s" % (mime, base64.b64encode(data).decode())

# ── 基础形状样式 ────────────────────────────────────────────────────────
SHAPE_STYLE = {
    "rectangle": "rounded=1;arcSize=8;",
    "roundRectangle": "rounded=1;arcSize=8;",
    "round": "ellipse;",
    "ellipse": "ellipse;",
    "text": "text;",
    "standardText": "text;",
    "diamond": "rhombus;",
    "triangle": "triangle;",
    "process": "rounded=0;",
    "terminator": "rounded=1;arcSize=50;",
    "comment": "shape=callout;size=6;position=0.15;position2=0.15;",  # 气泡注释
    "note": "shape=note;size=14;flipV=1;",
    "verticalPool": "rounded=0;",
    "basic_container": "rounded=1;arcSize=4;",
    "uiHLine": "line;",
    "singleRightArrow": "shape=arrow;",
    # Android / UI 控件
    "uiButton": "rounded=1;arcSize=12;",
    "andriodInput1": "rounded=1;arcSize=12;",
    "uiTextarea": "rounded=0;",
    "andriodTitle1": "rounded=0;",
    "andriodBlack1": "rounded=1;arcSize=3;",
    "andriodCheck": "rounded=1;arcSize=20;",
    "uiParagraph": "text;",
}
CONTAINER_STYLE = "rounded=0;"
# 容器类形状：保持自身造型，只做容器化处理
CONTAINER_SHAPE_STYLE = {
    "rectangle": "rounded=0;",
    "roundRectangle": "rounded=1;arcSize=8;",
    "verticalPool": "swimlane;horizontal=1;startSize=40;",
    "basic_container": "rounded=1;arcSize=4;",
    "andriodBlack1": "rounded=1;arcSize=3;",
}
DEFAULT_FILL = "#FFFFFF"
DEFAULT_STROKE = "#000000"
TEXT_KINDS = {"text", "standardText"}


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s or "0"


def _anchor_style(prefix, pt, rect, tol=3.0):
    """ProcessOn 的 from/to 坐标若贴在图形边框上，就钉死 drawio 的连接点。

    返回如 "exitX=0.5;exitY=1;exitPerimeter=0;"；不可靠时返回 ""（交给 drawio 自动锚定）。
    """
    if not pt or not rect:
        return ""
    x, y = _num(pt.get("x")), _num(pt.get("y"))
    bx, by, bw, bh = rect
    if bw <= 0 or bh <= 0:
        return ""
    rx, ry = (x - bx) / bw, (y - by) / bh
    if not (-0.05 <= rx <= 1.05 and -0.05 <= ry <= 1.05):
        return ""
    dx = min(abs(rx), abs(1 - rx)) * bw
    dy = min(abs(ry), abs(1 - ry)) * bh
    if min(dx, dy) > tol:
        return ""
    rx = max(0.0, min(1.0, rx))
    ry = max(0.0, min(1.0, ry))
    return f"{prefix}X={round(rx, 4)};{prefix}Y={round(ry, 4)};{prefix}Perimeter=0;"


def color_hex(raw):
    """ProcessOn 颜色 "r,g,b" / "r-50,g-50,b-50" -> #RRGGBB，非法返回 None。"""
    if raw is None:
        return None
    parts = [p.strip() for p in str(raw).split(",")]
    if len(parts) != 3:
        return None
    vals = []
    for p in parts:
        if re.match(r"^[a-zA-Z]", p):  # 相对主题色 r-50,g-50,b-50
            return None
        try:
            vals.append(max(0, min(255, int(round(float(p))))))
        except ValueError:
            return None
    return "#%02X%02X%02X" % tuple(vals)


def _xml_value(text):
    if not text:
        return ""
    text = (
        str(text)
        .replace("<div>", "\n")
        .replace("</div>", "")
        .replace("<br>", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
        .replace("&nbsp;", " ")
    )
    return escape(text).replace("\n", "&#10;")


def _dash_style(line_style):
    v = (line_style or {}).get("lineStyle")
    if v in ("dashed", "dash"):
        return "dashed=1;"
    if v == "dot":
        return "dashed=1;dashPattern=1 3;"
    if v == "dashdot":
        return "dashed=1;dashPattern=6 4 1 4;"
    return ""


def _font_style(font_style, default_size=12):
    f = font_style or {}
    style = f"fontSize={int(_num(f.get('size'), default_size))};"
    bits = 0
    if f.get("bold"):
        bits |= 1
    if f.get("italic"):
        bits |= 2
    if f.get("underline"):
        bits |= 4
    if bits:
        style += f"fontStyle={bits};"
    color = color_hex(f.get("color"))
    if color:
        style += f"fontColor={color};"
    if f.get("textAlign") in ("left", "center", "right"):
        style += f"align={f['textAlign']};"
    if f.get("vAlign") in ("top", "middle", "bottom"):
        va = "middle" if f["vAlign"] == "middle" else f["vAlign"]
        style += f"verticalAlign={va};"
    return style


def vertex_style(kind, e, is_container=False):
    """生成 mxCell style 字符串。"""
    path0 = (e.get("path") or [{}])[0]
    fs = e.get("fillStyle") or path0.get("fillStyle") or {}
    ls = e.get("lineStyle") or path0.get("lineStyle") or {}
    ft = e.get("fontStyle") or {}
    is_text = kind in TEXT_KINDS

    # 图片素材（ProcessOn 设计器图形库）：直接以 data URI 嵌入，最保真
    if fs.get("type") == "image":
        uri = image_data_uri(fs.get("fileId"))
        if uri:
            return "whiteSpace=wrap;html=1;shape=image;imageAspect=0;image=%s;%s" % (
                uri, _font_style(ft)
            )

    if is_container:
        style = CONTAINER_SHAPE_STYLE.get(kind) or CONTAINER_STYLE
    elif kind in SHAPE_STYLE:
        style = SHAPE_STYLE[kind]
    elif kind.startswith("andriod_icons") or kind.startswith("uiIcon"):
        style = "rounded=1;arcSize=20;"  # 图标站位的线框近似
    else:
        style = SHAPE_STYLE["rectangle"]
    style = "whiteSpace=wrap;html=1;" + style

    if not is_text:
        if fs.get("type") == "gradient":
            begin = color_hex(fs.get("beginColor")) or DEFAULT_FILL
            end = color_hex(fs.get("endColor")) or begin
            style += f"fillColor={begin};gradientColor={end};"
        else:
            fill = None if fs.get("type") == "none" else color_hex(fs.get("color"))
            if fs.get("type") == "none" or kind == "uiHLine":
                fill = "none"
            elif fill is None:
                fill = DEFAULT_FILL
            style += f"fillColor={fill or 'none'};"
    if not is_text:
        width = ls.get("lineWidth")
        if width == 0:
            style += "strokeColor=none;"
        else:
            stroke = color_hex(ls.get("lineColor")) or DEFAULT_STROKE
            style += f"strokeColor={stroke};"
            if width not in (None, 1):
                style += f"strokeWidth={int(_num(width, 1))};"
        style += _dash_style(ls)

    style += _font_style(ft)

    alpha = _num((e.get("shapeStyle") or {}).get("alpha"), 1)
    if 0 < alpha < 1:
        style += f"opacity={int(round(alpha * 100))};"

    if is_container and (e.get("textBlock") or [{}])[0].get("text"):
        style += "align=left;verticalAlign=top;spacingLeft=10;spacingTop=6;"

    return style


def edge_style(e):
    ls = e.get("lineStyle") or {}
    ft = e.get("fontStyle") or {}
    style = "edgeStyle=none;html=1;"
    if e.get("linkerType") == "curve":
        style += "curved=1;"
    else:
        style += "rounded=0;"

    width = ls.get("lineWidth")
    invisible = width == 0
    if invisible:
        style += "strokeColor=none;"
    else:
        stroke = color_hex(ls.get("lineColor")) or DEFAULT_STROKE
        style += f"strokeColor={stroke};"
        if width not in (None, 1):
            style += f"strokeWidth={int(_num(width, 1))};"
        style += _dash_style(ls)

    start = "block" if ls.get("beginArrowStyle") == "solidArrow" else "none"
    end = "none" if ls.get("endArrowStyle") == "none" else "block"
    if invisible:
        start = end = "none"
    style += f"startArrow={start};startFill={1 if start != 'none' else 0};"
    style += f"endArrow={end};endFill={1 if end != 'none' else 0};"
    style += _font_style(ft)
    if not invisible:
        style += "labelBackgroundColor=#FFFFFF;"
    return style


def _rect(e):
    p = e.get("props") or {}
    return (_num(p.get("x")), _num(p.get("y")), _num(p.get("w")), _num(p.get("h")))


def _contains(outer, inner, margin=1.0):
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return (
        ix >= ox - margin
        and iy >= oy - margin
        and ix + iw <= ox + ow + margin
        and iy + ih <= oy + oh + margin
    )


def convert(def_obj, name="Page-1"):
    elements = def_obj["elements"]
    page = def_obj.get("page") or {}

    vertices = [(k, e) for k, e in elements.items() if e.get("name") != "linker"]
    edges = [(k, e) for k, e in elements.items() if e.get("name") == "linker"]
    vertices.sort(key=lambda kv: _num((kv[1].get("props") or {}).get("zindex")))
    edges.sort(key=lambda kv: _num((kv[1].get("props") or {}).get("zindex")))

    all_rects = {k: _rect(e) for k, e in vertices}
    container_kinds = ("rectangle", "roundRectangle", "verticalPool", "basic_container", "andriodBlack1")

    # 容器：包含至少一个其它元素；大矩形面积需够大，泳道/容器形状直接认定
    containers = []
    for eid, e in vertices:
        kind = e.get("name")
        if kind not in container_kinds:
            continue
        r = all_rects[eid]
        area = r[2] * r[3]
        if kind in ("rectangle", "roundRectangle") and area < 15000:
            continue
        kids = [k2 for k2 in all_rects if k2 != eid and _contains(r, all_rects[k2], 2)]
        if kids:
            containers.append((eid, r, area))

    def parent_of(k, r):
        best = None
        for cid, cr, area in containers:
            if cid == k:
                continue
            if _contains(cr, r, 2):
                if best is None or area < best[1]:
                    best = (cid, area)
        return best[0] if best else None

    parent_rect = {cid: cr for cid, cr, _ in containers}

    rects = {k: _rect(e) for k, e in vertices}

    cells = []
    for eid, e in vertices:
        kind = e.get("name")
        x, y, w, h = _rect(e)
        parent = parent_of(eid, (x, y, w, h))
        ox, oy = (parent_rect[parent][:2] if parent else (0.0, 0.0))
        rx, ry = x - ox, y - oy
        text = (e.get("textBlock") or [{}])[0].get("text") or ""
        angle = _num((e.get("props") or {}).get("angle"))
        is_container = eid in parent_rect and kind in ("rectangle", "roundRectangle", "verticalPool", "basic_container", "andriodBlack1")
        style = vertex_style(kind, e, is_container)

        rot = ""
        if abs(angle) > 0.001:
            deg = round(angle * 180 / 3.141592653589793, 2)
            deg = deg % 360
            if deg:
                rot = f' rotation="{_fmt(deg)}"'

        cells.append(
            f'        <mxCell id={quoteattr(eid)} value={quoteattr(_xml_value(text))} '
            f"style={quoteattr(style)} vertex=\"1\" parent={quoteattr(parent or '1')}>\n"
            f'          <mxGeometry x="{_fmt(rx)}" y="{_fmt(ry)}" width="{_fmt(w)}" '
            f'height="{_fmt(h)}" as="geometry"{rot}/>\n'
            f"        </mxCell>"
        )

    for eid, e in edges:
        src = (e.get("from") or {}).get("id") or ""
        dst = (e.get("to") or {}).get("id") or ""
        pts, last = [], None
        for pt in e.get("points") or []:
            xy = (round(_num(pt.get("x")), 2), round(_num(pt.get("y")), 2))
            if xy != last:
                pts.append(xy)
            last = xy
        style = edge_style(e)
        style += _anchor_style("exit", e.get("from"), rects.get(src))
        style += _anchor_style("entry", e.get("to"), rects.get(dst))
        attrs = [
            f"id={quoteattr(eid)}",
            f'value={quoteattr(_xml_value(e.get("text")))}',
            f"style={quoteattr(style)}",
            'edge="1"',
            'parent="1"',
        ]
        if src in elements:
            attrs.append(f"source={quoteattr(src)}")
        if dst in elements:
            attrs.append(f"target={quoteattr(dst)}")
        body = ""
        if pts:
            rows = "\n".join(f'            <mxPoint x="{_fmt(px)}" y="{_fmt(py)}"/>' for px, py in pts)
            body = f'\n          <Array as="points">\n{rows}\n          </Array>\n        '
        cells.append(
            f'        <mxCell {" ".join(attrs)}>\n'
            f'          <mxGeometry relative="1" as="geometry">{body}</mxGeometry>\n'
            f"        </mxCell>"
        )

    allr = [_rect(e) for _, e in vertices]
    maxx = max((x + w for x, y, w, h in allr), default=800)
    maxy = max((y + h for x, y, w, h in allr), default=600)
    page_w = max(600, int(max(_num(page.get("width"), 0), maxx + 40)))
    page_h = max(400, int(maxy + 40))

    stamp = int(time.time() * 1000)
    diagram_id = "".join(random.choices(string.ascii_letters + string.digits, k=20))
    xml = (
        f'<mxfile host="ProcessOn" modified="{stamp}" agent="processon_to_drawio.py" '
        f'version="24.7.17" type="device">\n'
        f"  <diagram id=\"{diagram_id}\" name={quoteattr(name)}>\n"
        f'    <mxGraphModel dx="1200" dy="900" grid="1" gridSize="15" guides="1" '
        f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        f'pageWidth="{page_w}" pageHeight="{page_h}" math="0" shadow="0">\n'
        f"      <root>\n"
        f'        <mxCell id="0"/>\n'
        f'        <mxCell id="1" parent="0"/>\n'
        + "\n".join(cells)
        + "\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n"
    )
    return xml, len(vertices), len(edges), (page_w, page_h)


def load_def(path):
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict) and "def" in data and isinstance(data["def"], str):
        return json.loads(data["def"])
    if isinstance(data, dict) and "elements" in data:
        return data
    raise SystemExit(f"无法识别的 def 格式：{path}")


def main():
    ap = argparse.ArgumentParser(description="ProcessOn def -> drawio")
    ap.add_argument("def_json")
    ap.add_argument("-o", "--output")
    ap.add_argument("--name")
    args = ap.parse_args()

    def_obj = load_def(args.def_json)
    xml, nv, ne, size = convert(def_obj, args.name or "Page-1")
    out = args.output or (args.def_json.rsplit(".", 1)[0] + ".drawio")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(xml)
    print(f"✓ {out}  （{nv} 节点 / {ne} 连线 / 页面 {size[0]}x{size[1]}）")


if __name__ == "__main__":
    main()
