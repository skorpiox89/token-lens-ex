"""ProcessOn MCP Server（只读 · Token 认证）

把 ProcessOn「我的文件」里的图表读出来：文件树、图表定义（elements JSON）、
Mermaid / Markdown 大纲转换、批量导出。默认不做任何写操作。

接口（ProcessOn 网页端内部 API，JWT 登录态）：
    登录          POST https://www.processon.com/api/personal/login/v2/account
    我是谁        GET  /api/personal/user/info
    列文件        GET  /api/personal/folder/load_files?folderId=root&pageSize=...
    图定义 id     GET  /api/personal/canvas/get/chartdefids?chartId=...
    图定义        GET  /api/personal/diagraming/get/chart/def?chartId=...&defId=...
    导出额度/触发 GET  /api/personal/chart/export/get/user/power?chartId=...&exportType=jpghd
    分享链接      GET  /api/personal/chart/share/open?chartId=...   （唯一近似写操作）

运行前提：
    1. venv/bin/pip install "mcp>=1.2.0,<2"
    2. 浏览器登录 processon.com，F12 → Network → 任意 /api/personal/ 请求
       → Request Headers → 复制 token 的值（形如 eyJ...）写入 token.txt
       可选：配置 PROCESSON_ACCOUNT / PROCESSON_PASSWORD（或 login.json），
       token 过期时自动重登刷新；不配则过期后需手动更新 token.txt。
    3. venv/bin/python server.py  （stdio 传输）
"""

import base64
import hashlib
import html as _html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("processon")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.txt")
COOKIE_FILE = os.path.join(BASE_DIR, "cookie.txt")
LOGIN_FILE = os.path.join(BASE_DIR, "login.json")
EXPORT_DIR = os.path.join(BASE_DIR, "export")
DEF_DIR = os.path.join(EXPORT_DIR, "def")
DIAG_DIR = os.path.join(EXPORT_DIR, "diag")

# ProcessOn 网页端把 JWT 存在名为 token 的 cookie 里；凭证可能是裸 JWT（token.txt，
# 手动复制）或整段 cookie（cookie.txt，认证获取工具写入），这里统一取出 JWT。
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_COOKIE_TOKEN_RE = re.compile(r"(?:^|;\s*)token=([^;\s]+)")

WEB_BASE = "https://www.processon.com"
API = "/api/personal"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

MIN_INTERVAL = 0.35          # 请求最小间隔，降低风控概率
_last_call = {"t": 0.0}


class ProcessOnError(RuntimeError):
    def __init__(self, msg: str, body=None):
        super().__init__(msg)
        self.msg = msg
        self.body = body


class ProcessOnAuthError(ProcessOnError):
    pass


# ---------- 凭证 ----------

def _read_secret(value: str) -> str:
    """兼容 pi mcp.json 里 "!cat /path/file" 的写法。"""
    value = (value or "").strip()
    if value.startswith("!"):
        m = re.search(r"cat\s+(\S+)", value)
        if m and os.path.exists(m.group(1)):
            return open(m.group(1), encoding="utf-8").read().strip()
        return ""
    return value


def _extract_token(raw: str) -> str:
    """从裸 JWT 或整段 cookie（token=<jwt>）里取出 JWT。"""
    raw = (raw or "").strip().strip("'\"")
    if not raw:
        return ""
    m = _COOKIE_TOKEN_RE.search(raw)
    if m:
        return urllib.parse.unquote(m.group(1)).strip()
    m = _JWT_RE.search(raw)
    if m:
        return m.group(0)
    return raw if raw.startswith("eyJ") and raw.count(".") == 2 else ""


def _load_raw_credential() -> str:
    """按优先级取凭证：PROCESSON_TOKEN / PROCESSON_COOKIE 环境变量 → token.txt → cookie.txt。"""
    for name in ("PROCESSON_TOKEN", "PROCESSON_COOKIE"):
        v = _read_secret(os.environ.get(name, ""))
        if v:
            return v
    for path in (TOKEN_FILE, COOKIE_FILE):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                v = fh.read().strip()
            if v and not v.startswith("#"):
                return v
    return ""


def _load_token() -> str:
    tok = _extract_token(_load_raw_credential())
    if tok.lower().startswith("bearer "):
        tok = tok[7:].strip()
    return tok


def _save_token(tok: str) -> None:
    with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(tok + "\n")
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass


def _load_login() -> tuple:
    acc = _read_secret(os.environ.get("PROCESSON_ACCOUNT", ""))
    pwd = _read_secret(os.environ.get("PROCESSON_PASSWORD", ""))
    if (not acc or not pwd) and os.path.exists(LOGIN_FILE):
        try:
            cfg = json.load(open(LOGIN_FILE, encoding="utf-8"))
            acc = acc or (cfg.get("account") or "").strip()
            pwd = pwd or (cfg.get("password") or "").strip()
        except Exception:
            pass
    return acc, pwd


def _jwt_claims(tok: str) -> dict:
    try:
        payload = tok.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def _login() -> str:
    """账号密码换 JWT（密码 MD5 后传输），成功则写回 token.txt。"""
    acc, pwd = _load_login()
    if not acc or not pwd:
        raise ProcessOnAuthError(
            "token 缺失或已过期，且未配置 PROCESSON_ACCOUNT / PROCESSON_PASSWORD"
            f"（或 {LOGIN_FILE}），请在浏览器重新复制 token 到 {TOKEN_FILE}"
        )
    if not re.fullmatch(r"[0-9a-f]{32}", pwd.lower()):
        pwd = hashlib.md5(pwd.encode("utf-8")).hexdigest()
    payload = {
        "account": acc, "password": pwd,
        "userSource": "register", "businessType": "login",
        "registerType": "phone", "terminalType": "web", "channelType": "po",
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(WEB_BASE + API + "/login/v2/account", data=body, headers={
        "User-Agent": UA, "Content-Type": "application/json",
        "Referer": WEB_BASE + "/", "Origin": WEB_BASE,
        "Accept": "application/json, text/plain, */*",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ProcessOnAuthError(f"登录请求失败：{exc}")
    if str(out.get("code")) != "200":
        raise ProcessOnAuthError(f"登录失败：{out.get('msg') or out}")
    tok = (out.get("data") or {}).get("token")
    if not tok:
        raise ProcessOnAuthError("登录成功但未返回 token")
    _save_token(tok)
    return tok


# ---------- HTTP ----------

def _throttle() -> None:
    wait = MIN_INTERVAL - (time.time() - _last_call["t"])
    if wait > 0:
        time.sleep(wait)
    _last_call["t"] = time.time()


def _http(path: str, params: dict | None = None, method: str = "GET",
          data: dict | None = None, token: str = "", accept: str = "application/json, text/plain, */*"):
    if params:
        path = path + ("&" if "?" in path else "?") + urllib.parse.urlencode(params)
    url = path if path.startswith("http") else WEB_BASE + path
    body = urllib.parse.urlencode(data).encode("utf-8") if data else None
    headers = {
        "User-Agent": UA,
        "Referer": WEB_BASE + "/diagrams",
        "Origin": WEB_BASE,
        "Accept": accept,
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if token:
        headers["token"] = token
    if body:
        headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    _throttle()
    for attempt in range(2):  # GET 幂等，网络抖动重试一次
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            return exc.read(), dict(exc.headers)
        except Exception as exc:  # noqa: BLE001
            if attempt == 0:
                time.sleep(1.5)
                continue
            raise ProcessOnError(f"请求失败 {path}：{exc}")
    raise ProcessOnError(f"请求失败 {path}")


def _api(path: str, params: dict | None = None, method: str = "GET",
         data: dict | None = None, _retry: bool = True) -> dict:
    """调 /api/personal/*，返回 data 字段；鉴权失效时自动重登一次。"""
    token = _load_token()
    if not token:
        token = _login()
    raw, _ = _http(API + path, params=params, method=method, data=data, token=token)
    try:
        out = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ProcessOnError(f"{path} 返回无法解析（可能登录态失效）：{raw[:200]!r}")
    code = str(out.get("code"))
    if code == "200":
        return out.get("data") or {}
    if _retry and code in ("408", "403") and "鉴权" in str(out.get("msg", "")):
        _login()
        return _api(path, params=params, method=method, data=data, _retry=False)
    raise ProcessOnError(f"{path} 失败：{out.get('msg') or out}")


# ---------- 工具函数 ----------

def _pick(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return default


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _safe_name(name: str, fallback: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", (name or "").strip())[:60].strip("_ .")
    return name or fallback


def _norm_item(raw: dict, kind: str) -> dict:
    if kind == "folder":
        return {
            "kind": "folder",
            "title": _pick(raw, "title", "name", "folderName"),
            "folderId": str(_pick(raw, "folderId", "fileId", "id")),
            "updated": _pick(raw, "lastModify", "modifyTime", "updateTime", "createTime"),
        }
    return {
        "kind": "chart",
        "title": _pick(raw, "title", "name", "chartName"),
        "chartId": str(_pick(raw, "chartId", "fileId", "id", "definitionId")),
        "category": _pick(raw, "category", "type", "chartType", "fileType"),
        "updated": _pick(raw, "lastModify", "modifyTime", "updateTime", "createTime"),
    }


def _chart_url(chart_id: str, category: str = "") -> str:
    cat = (category or "").lower()
    if "mind" in cat:
        return f"{WEB_BASE}/mindmap/{chart_id}"
    if "outline" in cat:
        return f"{WEB_BASE}/outline/{chart_id}"
    return f"{WEB_BASE}/diagraming/{chart_id}"


def _list_files_raw(folder_id: str = "root", page: int = 1, page_size: int = 50) -> dict:
    return _api("/folder/load_files", {
        "folderId": folder_id, "sidx": "lastModify", "sort": "desc",
        "pageSize": page_size, "page": page,
    })


def _chart_def_raw(chart_id: str) -> dict:
    """返回 {chartId, defId, meta, kind, elements, tree, raw}。

    flow 类画布的 def 是 {elements:{...}, page, version}（元素 key == 元素 id）；
    mind/outline 类画布的 def 是一棵 {id, root, title, children[]} 大纲树。
    """
    cd = _api("/canvas/get/chartdefids", {"chartId": chart_id})
    canvas = cd.get("canvas") or {}
    def_id = canvas.get("mainCanvasId") or (
        (canvas.get("chartDefIds") or [{}])[0].get("definitionId"))
    if not def_id:
        raise ProcessOnError(f"未找到图表 {chart_id} 的 defId：{cd}")
    raw = _api("/diagraming/get/chart/def", {"chartId": chart_id, "defId": def_id})
    parsed = raw.get("def")
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    elements, tree, kind = {}, None, "elements"
    if isinstance(parsed.get("elements"), dict):
        elements = parsed["elements"]
    elif "children" in parsed or "leftChildren" in parsed or parsed.get("root"):
        tree, kind = parsed, "tree"
    else:
        elements = parsed
    return {
        "chartId": chart_id,
        "defId": def_id,
        "meta": (cd.get("chart") or {}),
        "kind": kind,
        "elements": elements,
        "tree": tree,
        "raw": raw,
    }


def _clean_text(text) -> str:
    """去 HTML 标签/实体、压缩空白（思维导图节点标题常带 <br>）。"""
    s = str(text or "")
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _el_text(el: dict) -> str:
    for tb in el.get("textBlock") or []:
        if isinstance(tb, dict) and tb.get("text"):
            return _clean_text(tb["text"])
        if isinstance(tb, str) and tb.strip():
            return _clean_text(tb)
    props = el.get("props") or {}
    # 不要拿 el["title"] 当文本：flow 形状的 title 是图形类型名（如「矩形」）
    return _clean_text(el.get("text") or props.get("text") or el.get("label") or "")


def _el_box(el: dict):
    p = el.get("props") or {}
    try:
        x = float(_pick(p, "x", "pinX", "left", default=0) or 0)
        y = float(_pick(p, "y", "pinY", "top", default=0) or 0)
        w = float(_pick(p, "w", "width", default=0) or 0)
        h = float(_pick(p, "h", "height", default=0) or 0)
    except (TypeError, ValueError):
        return None
    return (x, y, w, h)


def _el_parent(el: dict) -> str:
    p = el.get("props") or {}
    return str(_pick(el, "parentId", "pid", "parent", default="") or
               _pick(p, "parentId", "pid", "parent", default="") or "")


def _link_ends(link: dict) -> tuple:
    """尽力拿到 link 的两端 id（不同画布协议字段不一）。"""
    def pick_end(keys):
        for k in keys:
            v = link.get(k)
            if isinstance(v, dict):
                for kk in ("id", "elId", "elementId", "shapeId", "nodeId"):
                    if v.get(kk):
                        return str(v[kk])
            elif isinstance(v, (str, int)) and v != "":
                return str(v)
        return ""
    a = pick_end(("from", "source", "src", "start", "sourceId", "fromId", "startId"))
    b = pick_end(("to", "target", "dst", "end", "targetId", "toId", "endId"))
    return a, b


def _link_points(link: dict) -> list:
    pts = []
    for key in ("from", "to"):
        v = link.get(key)
        if isinstance(v, dict) and v.get("x") is not None:
            pts.append({"x": v.get("x"), "y": v.get("y")})
    for pt in link.get("points") or []:
        if isinstance(pt, dict) and pt.get("x") is not None:
            pts.append(pt)
    return pts


def _match_node(pt: dict, boxes: list):
    """按坐标找最近的节点（无 id 引用时的兜底）。"""
    try:
        px, py = float(pt.get("x")), float(pt.get("y"))
    except (TypeError, ValueError):
        return ""
    best, best_d = "", 1e18
    for nid, (x, y, w, h) in boxes:
        if x <= px <= x + w and y <= py <= y + h:
            return nid
        cx, cy = x + w / 2, y + h / 2
        d = (cx - px) ** 2 + (cy - py) ** 2
        if d < best_d:
            best, best_d = nid, d
    return best


def _mermaid_label(text: str, limit: int = 60) -> str:
    text = re.sub(r"[\r\n]+", " ", text or "").replace('"', "'").strip()
    if len(text) > limit:
        text = text[:limit - 1] + "…"
    return text


def _convert_flow(elements: dict, meta: dict) -> tuple:
    """flowbase 类 → mermaid flowchart。返回 (markdown, warnings)。"""
    warn = []
    nodes, links, containers = [], [], []
    for eid, el in elements.items():
        if not isinstance(el, dict):
            continue
        name = str(el.get("name", "")).lower()
        box = _el_box(el)
        if name in ("linker", "line", "connector", "edge") or (el.get("from") and el.get("to")):
            links.append((eid, el))
            continue
        if box is None or (box[2] <= 0 and box[3] <= 0):
            continue
        if (el.get("attribute") or {}).get("container"):
            containers.append((eid, el, box))
        nodes.append((eid, el, box))
    if not nodes:
        return "", ["未找到图形节点，可能是思维导图/大纲类，或 elements 结构未适配"]

    nid_map = {nid: f"n{i + 1}" for i, (nid, _, _) in enumerate(nodes)}
    lines = ["flowchart TD"]
    for nid, el, _ in nodes:
        label = _mermaid_label(_el_text(el)) or " "
        shape = str(el.get("name", "")).lower()
        if shape in ("decision", "diamond", "condition"):
            lines.append(f'    {nid_map[nid]}{{"{label}"}}')
        elif shape in ("terminator", "circle", "ellipse", "start", "end"):
            lines.append(f'    {nid_map[nid]}(["{label}"])')
        else:
            lines.append(f'    {nid_map[nid]}["{label}"]')
    boxes = [(nid, box) for nid, _, box in nodes]
    seen = set()
    for lid, link in links:
        a, b = _link_ends(link)
        pts = _link_points(link)
        if not a and pts:
            a = _match_node(pts[0], boxes)
            warn.append("") if False else None
        if not b and len(pts) > 1:
            b = _match_node(pts[-1], boxes)
        if not a or not b or a == b:
            continue
        if a not in nid_map or b not in nid_map:
            continue
        key = (a, b)
        label = _mermaid_label(_el_text(link), 30)
        if key in seen:
            continue
        seen.add(key)
        if label:
            lines.append(f'    {nid_map[a]} -->|"{label}"| {nid_map[b]}')
        else:
            lines.append(f"    {nid_map[a]} --> {nid_map[b]}")

    if containers:
        lines.append("")
        lines.append("%% 原图容器（分组框）：")
        for _, el, _ in containers:
            lines.append(f"%%   - {_el_text(el) or '未命名容器'}")

    if any(not _link_ends(l)[0] for _, l in links):
        warn.append("部分连线无 id 引用，已按坐标就近匹配，个别连线可能不准")
    return "\n".join(lines), warn


def _convert_outline(elements: dict, meta: dict) -> tuple:
    """mind / outline 类 → Markdown 大纲。返回 (markdown, warnings)。"""
    warn = []
    items = {}
    for eid, el in elements.items():
        if not isinstance(el, dict):
            continue
        name = str(el.get("name", "")).lower()
        if name in ("linker", "line", "connector", "edge") and _el_text(el) == "":
            continue
        text = _el_text(el)
        box = _el_box(el)
        if not text and box is None:
            continue
        items[eid] = {"text": text, "parent": _el_parent(el), "box": box,
                      "raw": el}
    if not items:
        return "", ["未找到大纲节点"]

    # 有 parentId 就用；否则用连线；再否则按 x 缩进
    children = {}
    has_parent = any(v["parent"] for v in items.values())
    if not has_parent:
        for eid, el in elements.items():
            if not isinstance(el, dict):
                continue
            if str(el.get("name", "")).lower() in ("linker", "line", "connector", "edge"):
                a, b = _link_ends(el)
                if a in items and b in items:
                    children.setdefault(a, []).append(b)
                    items[b]["parent"] = a
        has_parent = any(v["parent"] for v in items.values())

    lines = []
    if has_parent:
        for eid, v in items.items():
            if v["parent"] and v["parent"] in items:
                children.setdefault(v["parent"], []).append(eid)
        roots = [eid for eid in items if not (items[eid]["parent"] and items[eid]["parent"] in items)]

        def walk(eid, depth, path):
            if eid in path or depth > 12:
                return
            txt = items[eid]["text"] or eid
            lines.append("  " * depth + f"- {txt}")
            for c in children.get(eid, []):
                walk(c, depth + 1, path | {eid})

        for r in roots:
            walk(r, 0, set())
    else:
        warn.append("节点无父子字段，已按 x 坐标缩进推断层级")
        ordered = sorted(items.items(), key=lambda kv: (
            (kv[1]["box"][0] if kv[1]["box"] else 0),
            (kv[1]["box"][1] if kv[1]["box"] else 0)))
        xs = sorted({round(v["box"][0]) for _, v in ordered if v["box"]})
        for eid, v in ordered:
            x = v["box"][0] if v["box"] else 0
            depth = sum(1 for lv in xs if lv < x - 5)
            lines.append("  " * min(depth, 10) + f"- {v['text'] or eid}")
    return "\n".join(lines), warn


def _convert_mind_tree(tree: dict) -> tuple:
    """mind/outline 画布的大纲树 → Markdown 嵌套列表。返回 (markdown, warnings)。"""
    lines = []
    root_title = _clean_text(tree.get("title"))
    if root_title:
        lines.append(f"- {root_title}")

    def walk(node, depth: int):
        if depth > 14 or not isinstance(node, dict):
            return
        title = _clean_text(node.get("title"))
        if title:
            lines.append("  " * depth + f"- {title}")
        for ch in node.get("children") or []:
            walk(ch, depth + 1)

    base = 1 if root_title else 0
    branches = list(tree.get("children") or []) + list(tree.get("leftChildren") or [])
    for ch in branches:
        walk(ch, base)
    if not lines:
        return "", ["大纲树为空"]
    return "\n".join(lines), []


def _mindmap_text(text) -> str:
    """mermaid mindmap 节点文本：括号/方括号会被当成形状语法，替换为全角。"""
    s = _clean_text(text)
    for a, b in (("(", "（"), (")", "）"), ("[", "【"), ("]", "】"),
                 ("{", "｛"), ("}", "｝")):
        s = s.replace(a, b)
    s = re.sub(r"::+", "：", s)
    return s[:120]


def _convert_mind_mermaid(tree: dict) -> tuple:
    """mind/outline 大纲树 → mermaid mindmap（思源 3.8 内置 mermaid 11 直接渲染）。

    缩进即层级：根节点 2 空格，子级每层 +2。返回 (mermaid, warnings)。
    """
    lines = ["mindmap"]
    root = _mindmap_text(tree.get("title")) or "ProcessOn"
    lines.append("  " + root)
    count = {"n": 0}

    def walk(node, depth: int):
        if depth > 12 or not isinstance(node, dict):
            return
        title = _mindmap_text(node.get("title"))
        if title:
            lines.append("  " * (depth + 1) + title)
            count["n"] += 1
        for ch in node.get("children") or []:
            walk(ch, depth + 1)

    for ch in list(tree.get("children") or []) + list(tree.get("leftChildren") or []):
        walk(ch, 1)
    if count["n"] == 0:
        return "", ["大纲树为空"]
    return "\n".join(lines), []


def _convert_chart(chart_id: str, meta: dict, definfo: dict) -> dict:
    tree = (definfo or {}).get("tree")
    elements = (definfo or {}).get("elements") or {}
    if tree:
        # 思维导图：正文用 mermaid mindmap（可渲染成图），另附大纲文本便于阅读/搜索
        body, warn = _convert_mind_mermaid(tree)
        outline, owarn = _convert_mind_tree(tree)
        if not body:
            body, warn = outline, owarn
            outline = ""
        return {"format": "mermaid" if body else "text", "body": body,
                "outline": outline if outline != body else "",
                "warnings": [w for w in (warn + owarn) if w]}
    category = str(_pick(meta, "category", "type", "chartType", "fileType", default="")).lower()
    is_mind = any(k in category for k in ("mind", "outline", "free"))
    if not category:
        names = {str((e or {}).get("name", "")).lower() for e in elements.values() if isinstance(e, dict)}
        is_mind = bool(names & {"mind", "mind_node", "topic", "mindmap"}) or (
            "root" in elements and "linker" not in names)
    if is_mind:
        body, warn = _convert_outline(elements, meta)
        fmt = "outline"
    else:
        body, warn = _convert_flow(elements, meta)
        fmt = "mermaid"
    if not body:
        body, warn2 = _convert_outline(elements, meta)
        warn = warn + warn2 if body else warn
        fmt = "outline" if body else "text"
    if not body:
        texts = [f"- {_el_text(e)}" for e in elements.values()
                 if isinstance(e, dict) and _el_text(e)]
        body = "\n".join(texts)
        fmt = "text"
    return {"format": fmt, "body": body, "warnings": [w for w in warn if w]}


# ---------- MCP 工具 ----------

@mcp.tool()
def check_auth() -> str:
    """检查 token 是否有效，返回当前登录的 ProcessOn 账号信息。

    同时显示 token 到期时间；若配置了账号密码，过期后会自动重登。
    """
    tok = _load_token()
    claims = _jwt_claims(tok)
    exp = claims.get("exp") or 0
    info = {}
    try:
        info = _api("/user/info") or {}
    except ProcessOnError as exc:
        return _dumps({"ok": False, "error": exc.msg,
                       "tokenFile": TOKEN_FILE,
                       "hasLoginFallback": bool(_load_login()[0])})
    return _dumps({
        "ok": True,
        "userId": _pick(info, "userId", "id") or claims.get("userId", ""),
        "nickName": _pick(info, "nickName", "fullName", "userName", "name") or claims.get("fullName", ""),
        "account": _pick(info, "account", "phone", "email"),
        "tokenExp": exp or None,
        "tokenExpText": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(exp)) if exp else "",
        "daysLeft": round((exp - time.time()) / 86400, 1) if exp else None,
        "vip": _pick(info, "vip", "isVip", "vipType", default=None),
        "raw": info if not _pick(info, "nickName", "fullName", "userName", "name") else None,
    })


@mcp.tool()
def list_files(folder_id: str = "root", page: int = 1, page_size: int = 100,
               all_pages: bool = False) -> str:
    """列出「我的文件」某个文件夹里的图表和子文件夹。

    Args:
        folder_id: 文件夹 id，"root" 为顶层（默认）
        page: 页码，从 1 开始
        page_size: 每页数量；服务端可能封顶（默认 100）
        all_pages: True 时自动翻页取完该文件夹所有内容
    """
    folders, charts, sample, pages_done = [], [], None, 0
    p = max(1, page)
    try:
        while True:
            data = _list_files_raw(folder_id, p, max(1, min(page_size, 500)))
            pages_done += 1
            fs = data.get("folders") or data.get("folderList") or []
            cs = data.get("charts") or data.get("chartList") or data.get("files") or []
            if sample is None and (fs or cs):
                first = (fs or cs)[0]
                sample = sorted(first.keys()) if isinstance(first, dict) else [type(first).__name__]
            folders += [_norm_item(x, "folder") for x in fs if isinstance(x, dict)]
            charts += [_norm_item(x, "chart") for x in cs if isinstance(x, dict)]
            got = len(fs) + len(cs)
            if not all_pages or got == 0 or got < max(1, min(page_size, 500)):
                break
            p += 1
            if p > 60:
                break
    except ProcessOnError as exc:
        return _dumps({"ok": False, "error": exc.msg})
    return _dumps({
        "ok": True, "folderId": folder_id, "page": page, "pagesRead": pages_done,
        "folders": folders, "charts": charts,
        "count": {"folders": len(folders), "charts": len(charts)},
        "totalHint": sorted((data or {}).keys()) if isinstance(data, dict) else None,
        "sampleKeys": sample,
    })


@mcp.tool()
def list_tree(folder_id: str = "root", max_depth: int = 4, max_items: int = 500) -> str:
    """递归列出「我的文件」目录树（Markdown 缩进格式，含 id，便于后续按 id 读取）。

    Args:
        folder_id: 起始文件夹，"root" 为顶层
        max_depth: 最大递归深度（默认 4）
        max_items: 最多列出多少个条目（防跑飞，默认 500）
    """
    out = [f"ProcessOn 我的文件（含 id）"]
    counter = {"n": 0}
    truncated = {"v": False}

    def walk(fid: str, depth: int, prefix: str):
        if depth > max_depth or truncated["v"]:
            return
        data = _list_files_raw(fid, 1, 200)
        fs = data.get("folders") or data.get("folderList") or []
        cs = data.get("charts") or data.get("chartList") or data.get("files") or []
        for f in fs:
            if not isinstance(f, dict) or truncated["v"]:
                continue
            item = _norm_item(f, "folder")
            counter["n"] += 1
            if counter["n"] > max_items:
                truncated["v"] = True
                return
            out.append(f"{'  ' * depth}📁 {item['title']}  (folderId={item['folderId']})")
            walk(item["folderId"], depth + 1, prefix)
        for c in cs:
            if not isinstance(c, dict) or truncated["v"]:
                continue
            item = _norm_item(c, "chart")
            counter["n"] += 1
            if counter["n"] > max_items:
                truncated["v"] = True
                return
            cat = f" [{item['category']}]" if item["category"] else ""
            upd = f"  {item['updated']}" if item["updated"] else ""
            out.append(f"{'  ' * depth}📄 {item['title']}{cat}  (chartId={item['chartId']}){upd}")

    try:
        walk(folder_id, 0, "")
    except ProcessOnError as exc:
        return _dumps({"ok": False, "error": exc.msg})
    if truncated["v"]:
        out.append(f"… 已达 max_items={max_items} 上限，未列完")
    out.append(f"\n共 {counter['n']} 个条目" + ("（截断）" if truncated["v"] else ""))
    return "\n".join(out)


@mcp.tool()
def get_chart_def(chart_id: str, save: bool = True) -> str:
    """读取一张图的完整定义（elements JSON），返回元素统计 + 文本清单。

    Args:
        chart_id: 图表 id（list_files / list_tree 里拿）
        save: 是否把原始 JSON 存到 export/def/<chartId>.json（默认存，便于后续精确转换）
    """
    try:
        info = _chart_def_raw(chart_id)
    except ProcessOnError as exc:
        return _dumps({"ok": False, "error": exc.msg})
    elements = info["elements"]
    tree = info.get("tree")
    kinds = {}
    texts = []
    if tree:
        stack = [(tree, 0)]
        while stack:
            node, depth = stack.pop()
            if not isinstance(node, dict):
                continue
            title = _clean_text(node.get("title"))
            if title:
                texts.append({"id": str(node.get("id", "")), "name": "node",
                              "text": title[:120], "depth": depth})
            for ch in list(node.get("children") or []) + list(node.get("leftChildren") or []):
                stack.append((ch, depth + 1))
        kinds = {"node": len(texts)}
    else:
        for eid, el in elements.items():
            if not isinstance(el, dict):
                continue
            name = str(el.get("name", "?"))
            kinds[name] = kinds.get(name, 0) + 1
            t = _el_text(el)
            if t:
                texts.append({"id": eid, "name": name, "text": t[:120]})
    saved = ""
    if save:
        os.makedirs(DEF_DIR, exist_ok=True)
        saved = os.path.join(DEF_DIR, f"{_safe_name(chart_id, 'chart')}.json")
        with open(saved, "w", encoding="utf-8") as fh:
            json.dump(info["raw"], fh, ensure_ascii=False, indent=2)
    return _dumps({
        "ok": True, "chartId": chart_id, "defId": info["defId"],
        "title": _pick(info["meta"], "title", "name"),
        "category": _pick(info["meta"], "category", "type", "chartType"),
        "elementCount": len(texts) if tree else len(elements), "kindCounts": kinds,
        "defKind": info.get("kind"),
        "texts": texts[:80], "textsTruncated": len(texts) > 80,
        "savedTo": saved,
    })


@mcp.tool()
def chart_to_markdown(chart_id: str, save: bool = False) -> str:
    """把一张图转成可编辑文本：流程/架构类 → Mermaid，思维导图/大纲类 → Markdown 大纲。

    Args:
        chart_id: 图表 id
        save: 是否把转换结果存到 export/md/<chartId>.md
    """
    try:
        info = _chart_def_raw(chart_id)
    except ProcessOnError as exc:
        return _dumps({"ok": False, "error": exc.msg})
    conv = _convert_chart(chart_id, info["meta"], info)
    title = _pick(info["meta"], "title", "name", default=chart_id)
    category = _pick(info["meta"], "category", "type", "chartType")
    doc = [f"# {title}", "", f"> ProcessOn: {_chart_url(chart_id, str(category))}", ""]
    if conv["format"] == "mermaid":
        doc += ["```mermaid", conv["body"], "```"]
    else:
        doc += [conv["body"]]
    markdown = "\n".join(doc)
    if conv.get("outline"):
        markdown += "\n\n## 大纲\n\n" + conv["outline"]
    saved = ""
    if save and conv["format"] != "text":
        os.makedirs(os.path.join(EXPORT_DIR, "md"), exist_ok=True)
        saved = os.path.join(EXPORT_DIR, "md", f"{_safe_name(chart_id, 'chart')}.md")
        with open(saved, "w", encoding="utf-8") as fh:
            fh.write(markdown + "\n")
    return _dumps({
        "ok": True, "chartId": chart_id, "title": title,
        "category": category, "url": _chart_url(chart_id, str(category)),
        "format": conv["format"], "markdown": markdown,
        "warnings": conv["warnings"], "savedTo": saved,
    })


@mcp.tool()
def export_chart_image(chart_id: str, fmt: str = "jpg") -> str:
    """[BETA] 触发 ProcessOn 服务端导出并尝试下载高分辨率图片到 export/img/。

    走 /chart/export/get/user/power（exportType=jpghd）；若接口返回的是异步任务，
    会把原始返回存到 export/diag/ 方便进一步定位，不会静默失败。

    Args:
        chart_id: 图表 id
        fmt: jpg / png / pdf
    """
    try:
        data = _api("/chart/export/get/user/power",
                    {"chartId": chart_id, "exportType": "jpghd" if fmt == "jpg" else fmt})
    except ProcessOnError as exc:
        return _dumps({"ok": False, "error": exc.msg})

    def find_url(obj):
        if isinstance(obj, str):
            if obj.startswith("http") and re.search(r"\.(jpg|jpeg|png|svg|pdf)($|\?)", obj, re.I):
                return obj
            return ""
        if isinstance(obj, dict):
            for v in obj.values():
                u = find_url(v)
                if u:
                    return u
        if isinstance(obj, list):
            for v in obj:
                u = find_url(v)
                if u:
                    return u
        return ""

    url = find_url(data)
    diag = os.path.join(DIAG_DIR, f"{_safe_name(chart_id, 'chart')}_export.json")
    os.makedirs(DIAG_DIR, exist_ok=True)
    with open(diag, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    if not url:
        return _dumps({"ok": False, "stage": "no-url",
                       "hint": "接口已返回但未找到下载地址（可能是异步任务/需额外参数）",
                       "rawKeys": sorted(data.keys()) if isinstance(data, dict) else None,
                       "diag": diag})
    raw, headers = _http(url, token=_load_token())
    ctype = (headers.get("Content-Type") or "").lower()
    if "image" not in ctype and "pdf" not in ctype:
        return _dumps({"ok": False, "stage": "download", "url": url,
                       "contentType": ctype, "diag": diag})
    ext = "pdf" if "pdf" in ctype else ("png" if "png" in ctype else "jpg")
    out_dir = os.path.join(EXPORT_DIR, "img")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{_safe_name(chart_id, 'chart')}.{ext}")
    with open(path, "wb") as fh:
        fh.write(raw)
    return _dumps({"ok": True, "chartId": chart_id, "url": url,
                   "file": path, "bytes": len(raw), "contentType": ctype})


@mcp.tool()
def share_chart(chart_id: str) -> str:
    """开启（或复用）该图的公开分享链接，返回可点击的 view 链接。

    注意：这是本 Server 唯一的写操作（幂等，开启后图将可通过链接公开访问），
    只在确实需要「原图入口」时调用。
    """
    try:
        data = _api("/chart/share/open", {"chartId": chart_id})
    except ProcessOnError as exc:
        return _dumps({"ok": False, "error": exc.msg})
    link_id = _pick(data, "viewLinkId", "viewLinkID", "linkId", "id")
    if not link_id and isinstance(data, str):
        link_id = data
    return _dumps({"ok": bool(link_id), "chartId": chart_id,
                   "shareUrl": f"{WEB_BASE}/view/link/{link_id}" if link_id else "",
                   "raw": data if not link_id else None})


@mcp.tool()
def export_folder(folder_id: str = "root", max_charts: int = 50,
                  with_markdown: bool = True, out_dir: str = "") -> str:
    """把一个文件夹（含子文件夹）里的图批量导出：原始 JSON + Markdown 转换 + index.md。

    单次上限 max_charts 张，避免 MCP 调用超时；超量时分批跑。
    结果可直接作为导入思源的素材。

    Args:
        folder_id: 起始文件夹，"root" 为顶层
        max_charts: 本次最多导出多少张图（默认 50）
        with_markdown: 是否同时生成 Markdown / Mermaid 转换
        out_dir: 自定义输出目录，默认 export/archive-<时间戳>
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root_out = out_dir or os.path.join(EXPORT_DIR, f"archive-{stamp}")
    def_out = os.path.join(root_out, "def")
    md_out = os.path.join(root_out, "md")
    os.makedirs(def_out, exist_ok=True)
    if with_markdown:
        os.makedirs(md_out, exist_ok=True)

    collected = []          # (folder_path, item)
    errors = []
    truncated = {"v": False}

    def walk(fid: str, path: list, depth: int):
        if depth > 6 or truncated["v"]:
            return
        data = _list_files_raw(fid, 1, 200)
        for f in (data.get("folders") or data.get("folderList") or []):
            if not isinstance(f, dict):
                continue
            it = _norm_item(f, "folder")
            walk(it["folderId"], path + [it["title"] or it["folderId"]], depth + 1)
        for c in (data.get("charts") or data.get("chartList") or data.get("files") or []):
            if not isinstance(c, dict):
                continue
            if len(collected) >= max_charts:
                truncated["v"] = True
                return
            collected.append((list(path), _norm_item(c, "chart")))

    try:
        walk(folder_id, [], 0)
    except ProcessOnError as exc:
        return _dumps({"ok": False, "error": exc.msg})

    index = [f"# ProcessOn 归档（{stamp}）", "",
             f"来源 folder: {folder_id}，共 {len(collected)} 张图", ""]
    ok = 0
    for path, item in collected:
        cid = item["chartId"]
        title = item["title"] or cid
        rel = "/".join(path + [title])
        try:
            info = _chart_def_raw(cid)
            fn = _safe_name(f"{cid}_{title}", cid)
            with open(os.path.join(def_out, fn + ".json"), "w", encoding="utf-8") as fh:
                json.dump(info["raw"], fh, ensure_ascii=False, indent=2)
            md_rel = ""
            if with_markdown:
                conv = _convert_chart(cid, info["meta"], info)
                lines = [f"# {title}", "",
                         f"> ProcessOn: {_chart_url(cid, str(item['category']))}", ""]
                if conv["format"] == "mermaid":
                    lines += ["```mermaid", conv["body"], "```"]
                else:
                    lines += [conv["body"]]
                if conv.get("outline"):
                    lines += ["", "## 大纲", "", conv["outline"]]
                if conv["warnings"]:
                    lines += ["", "<!-- 转换提示：" + "；".join(conv["warnings"]) + " -->"]
                with open(os.path.join(md_out, fn + ".md"), "w", encoding="utf-8") as fh:
                    fh.write("\n".join(lines) + "\n")
                md_rel = f"md/{fn}.md"
            index.append(f"- [{rel}]({md_rel or 'def/' + fn + '.json'})  "
                         f"`{cid}`  {item['category']}  {item['updated']}")
            ok += 1
        except ProcessOnError as exc:
            errors.append({"chartId": cid, "title": title, "error": exc.msg})
            index.append(f"- {rel}  `{cid}`  ⚠️ 读取失败：{exc.msg}")
    index += ["", f"成功 {ok} / {len(collected)}" +
              ("，已达 max_charts 上限（可能还有更多，请分批）" if truncated["v"] else "")]
    with open(os.path.join(root_out, "index.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(index) + "\n")
    return _dumps({"ok": True, "outDir": root_out, "exported": ok,
                   "attempted": len(collected), "errors": errors,
                   "truncated": truncated["v"], "index": os.path.join(root_out, "index.md")})


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        try:
            print(check_auth())
            print(list_files(page_size=5))
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}", file=sys.stderr)
            raise SystemExit(1)
        raise SystemExit(0)
    mcp.run(transport="stdio")
