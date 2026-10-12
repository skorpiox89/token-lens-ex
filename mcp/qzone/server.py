"""QQ空间 MCP Server（只读 · Cookie 认证）

仅提供读取能力：说说、日志（文章）、相册/相片，不做任何写操作。

接口路径、参数与 g_tk 算法移植自 ShunCai/QZoneExport（MIT License）
https://github.com/ShunCai/QZoneExport  （core/qzone-api/*）

运行前提：
    1. pip install "mcp>=1.2.0,<2"
    2. 浏览器登录 user.qzone.qq.com，复制整段 cookie 到 cookie.txt（或 QZONE_COOKIE）
    3. python server.py  （stdio 传输）
"""

import html as _html
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("qzone")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# ---------- 接口地址（QZoneExport core/qzone-api/urls.ts） ----------
USER_INFO_URL = "https://user.qzone.qq.com/proxy/domain/base.qzone.qq.com/cgi-bin/user/cgi_userinfo_get_all"
MESSAGES_LIST_URL = "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6"
MESSAGES_DETAIL_URL = "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msgdetail_v6"
MESSAGES_IMAGES_URL = "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_get_pics_v6"
BLOGS_LIST_URL = "https://user.qzone.qq.com/proxy/domain/b.qzone.qq.com/cgi-bin/blognew/get_abs"
BLOGS_INFO_URL = "https://user.qzone.qq.com/proxy/domain/b.qzone.qq.com/cgi-bin/blognew/blog_output_data"
ALBUM_LIST_URL = "https://user.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/fcg_list_album_v3"
IMAGES_LIST_URL = "https://user.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/cgi_list_photo"

_token_cache = {"token": "", "ts": 0.0}


# ---------- Cookie / 鉴权 ----------

def _cookie() -> str:
    cookie = os.environ.get("QZONE_COOKIE", "").strip()
    if not cookie:
        raise RuntimeError("未配置 QZONE_COOKIE：请把浏览器里 qzone 的整段 cookie 写入 cookie.txt")
    return cookie


def _cookie_map() -> dict:
    out = {}
    for part in _cookie().split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def _owner_uin() -> str:
    raw = _cookie_map().get("uin") or _cookie_map().get("p_uin") or ""
    m = re.search(r"\d+", raw)
    if not m:
        raise RuntimeError("cookie 中没有 uin，请确认复制了完整的 qzone 登录 cookie")
    return m.group(0)


def _gtk() -> int:
    """g_tk（QQ空间 CSRF Token），算法同 QZoneExport calcGtk"""
    cm = _cookie_map()
    skey = cm.get("p_skey") or cm.get("skey") or cm.get("rv2") or ""
    if not skey:
        raise RuntimeError("cookie 中没有 p_skey/skey，无法计算 g_tk")
    h = 5381
    for ch in skey:
        h = (h + (h << 5) + ord(ch)) & 0xFFFFFFFF
    return h & 0x7FFFFFFF


def _qzonetoken() -> str:
    """从空间首页 HTML 中提取 qzonetoken，缓存 30 分钟"""
    now = time.time()
    if _token_cache["token"] and now - _token_cache["ts"] < 1800:
        return _token_cache["token"]
    page = _fetch(f"https://user.qzone.qq.com/{_owner_uin()}")
    compact = page.replace(" ", "")
    token = ""
    idx = compact.find("window.g_qzonetoken")
    if idx != -1:
        m = re.search(r'return"(\w*?)";', compact[idx:])
        if m:
            token = m.group(1)
    _token_cache.update(token=token, ts=now)
    return token


# ---------- 请求 ----------

def _fetch(url: str, params: dict | None = None, charset: str = "utf-8") -> str:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Cookie": _cookie(),
        "User-Agent": UA,
        "Referer": f"https://user.qzone.qq.com/{_owner_uin()}",
        "Accept": "*/*",
    })
    last_err = None
    for attempt in range(2):  # GET 幂等，超时重试一次
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"QQ空间接口返回错误 {e.code}: {detail[:200]}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt == 0:
                time.sleep(1)
                continue
    raise RuntimeError(f"无法连接 QQ空间: {getattr(last_err, 'reason', last_err)}")


def _unwrap(text: str):
    """去掉 JSONP 外壳（_preloadCallback(...) / shine0_Callback(...) / _Callback(...)）"""
    t = text.strip()
    m = re.match(r"^[A-Za-z_][\w.]*\s*\(([\s\S]*)\)\s*;?\s*$", t)
    if m:
        t = m.group(1)
    return json.loads(t)


def _get_json(url: str, params: dict, charset: str = "utf-8"):
    return _unwrap(_fetch(url, params, charset=charset))


def _photo_ts() -> str:
    """相册接口的时间戳参数（QZoneExport photoTimestamp 的等价实现）"""
    s = f"{random.random():.16f}"[-9:]
    return "9" + s[1:] if s.startswith("0") else s


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h[1-6]>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def _extract_div(page: str, div_id: str) -> str | None:
    """提取指定 id 的 div 内容（支持嵌套 div）"""
    m = re.search(r'<div[^>]*id="%s"[^>]*>' % re.escape(div_id), page)
    if not m:
        return None
    start = m.end()
    depth = 1
    for t in re.finditer(r"<(/?)div\b[^>]*>", page[start:], re.I):
        if t.group(1):
            depth -= 1
            if depth == 0:
                return page[start:start + t.start()]
        else:
            depth += 1
    return page[start:]


def _js_string_decode(raw: str) -> str:
    """解码 JS 单引号字符串字面量（模板日志用）"""
    raw = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), raw)
    return (raw.replace("\\'", "'")
            .replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
            .replace("\\/", "/"))


# ---------- 数据裁剪 ----------

def _trim_pic(p: dict) -> dict:
    out = {}
    for k in ("url1", "url2", "url3", "is_video", "video_url"):
        if p.get(k) is not None:
            out[k] = p[k]
    return out


def _trim_comment(c: dict) -> dict:
    return {
        "nick": (c.get("user") or {}).get("nickname") or c.get("nick"),
        "content": c.get("content"),
        "createTime": c.get("createTime") or c.get("create_time") or c.get("postTime"),
        "replies": [_trim_comment(r) for r in (c.get("replys") or c.get("replies") or [])],
    }


def _trim_msg(m: dict) -> dict:
    return {
        "tid": m.get("tid"),
        "content": m.get("content"),
        "created_time": m.get("created_time"),
        "commenttotal": m.get("commenttotal"),
        "imagetotal": m.get("imagetotal"),
        "has_more_con": m.get("has_more_con"),
        "lbs": (m.get("lbs") or {}).get("name"),
        "pics": [_trim_pic(p) for p in (m.get("pic") or [])],
        "rt_con": m.get("rt_con"),
    }


def _trim_photo(p: dict) -> dict:
    def trim(u):
        if not u:
            return None
        for token in ("?t=5&", "?t=5", "&t=5"):
            if token in u:
                return u.replace(token, "?" if token == "?t=5&" else "")
        return u

    raw = p.get("raw") if p.get("raw_upload") == 1 else None
    origin = (p.get("origin_url") if p.get("origin_upload") == 1 else None) or p.get("origin")
    normal = p.get("downloadUrl") or p.get("url")
    return {
        "name": p.get("name"),
        "desc": p.get("desc"),
        "uploadTime": p.get("uploadTime") or p.get("uploadtime"),
        "width": p.get("width"),
        "height": p.get("height"),
        "url": trim(normal),
        "original": trim(origin),
        "raw": trim(raw),
        "pre": p.get("pre"),
        "is_video": p.get("is_video"),
        "video_url": p.get("video_url"),
    }


def _trim_album(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "name": a.get("name"),
        "desc": a.get("desc"),
        "total": a.get("total"),
        "pre": a.get("pre"),
        "url": a.get("url"),
        "classid": a.get("classid"),
        "createtime": a.get("createtime"),
        "modifytime": a.get("modifytime"),
    }


# ---------- MCP 工具（只读） ----------

@mcp.tool()
def check_auth() -> str:
    """检查 Cookie 是否有效，返回当前空间主人的资料（昵称、QQ 号等）"""
    data = _get_json(USER_INFO_URL, {
        "uin": _owner_uin(), "vuin": _owner_uin(), "fupdate": 1,
        "rd": random.random(), "g_tk": _gtk(), "qzonetoken": _qzonetoken(),
    })
    return _dumps(data)


@mcp.tool()
def list_shuoshuo(pos: int = 0, num: int = 20) -> str:
    """读取说说列表（按时间倒序）

    Args:
        pos: 从第几条开始（分页），默认 0
        num: 每页条数，默认 20，最大 40
    """
    num = max(1, min(int(num), 40))
    data = _get_json(MESSAGES_LIST_URL, {
        "uin": _owner_uin(), "ftype": 0, "sort": 0, "pos": int(pos), "num": num,
        "replynum": 100, "g_tk": _gtk(), "callback": "_preloadCallback",
        "code_version": 1, "format": "jsonp", "need_private_comment": 1,
        "qzonetoken": _qzonetoken(),
    })
    items = [_trim_msg(m) for m in (data.get("msglist") or [])]
    return _dumps({"total": data.get("total"), "pos": int(pos), "items": items})


@mcp.tool()
def get_shuoshuo(tid: str) -> str:
    """读取单条说说的全文（列表里的 content 可能被截断）与评论

    Args:
        tid: 说说 ID（list_shuoshuo 返回的 tid）
    """
    data = _get_json(MESSAGES_DETAIL_URL, {
        "qzonetoken": _qzonetoken(), "g_tk": _gtk(), "tid": str(tid),
        "uin": _owner_uin(), "t1_source": 1, "not_trunc_con": 1,
        "hostuin": _owner_uin(), "code_version": 1, "format": "jsonp",
        "qzreferrer": "https://user.qzone.qq.com",
    })
    # 图片总数大于列表内数量时，补拉完整图片地址
    pic = data.get("pic") or []
    total = data.get("imagetotal") or 0
    if total > len(pic):
        img = _get_json(MESSAGES_IMAGES_URL, {
            "r": random.random(), "tid": str(tid), "uin": _owner_uin(),
            "t1_source": 1, "random": random.random(), "g_tk": _gtk(),
            "qzonetoken": _qzonetoken(),
        })
        pic = [{"url3": u, "url2": u, "url1": u} for u in (img.get("imageUrls") or [])] or pic
    return _dumps({
        "tid": str(tid),
        "content": data.get("content"),
        "created_time": data.get("created_time"),
        "rt_con": data.get("rt_con"),
        "pics": [_trim_pic(p) for p in pic],
        "comments": [_trim_comment(c) for c in (data.get("conlist") or [])],
    })


@mcp.tool()
def list_blogs(pos: int = 0, num: int = 20) -> str:
    """读取日志（文章）列表（按时间倒序）

    Args:
        pos: 从第几条开始（分页），默认 0
        num: 每页条数，默认 20，最大 40
    """
    num = max(1, min(int(num), 40))
    data = _get_json(BLOGS_LIST_URL, {
        "hostUin": _owner_uin(), "uin": _owner_uin(), "blogType": "0",
        "cateName": "", "cateHex": "", "statYear": time.localtime().tm_year,
        "reqInfo": "7", "pos": int(pos), "num": num, "sortType": "0",
        "absType": "1", "source": "0", "rand": random.random(), "ref": "qzone",
        "g_tk": _gtk(), "verbose": "1", "qzonetoken": _qzonetoken(),
    }, charset="gbk")
    d = data.get("data") or {}
    items = []
    for b in (d.get("list") or []):
        items.append({
            "blogid": b.get("blogid") or b.get("blogId"),
            "title": b.get("title"),
            "pubtime": b.get("pubTime") or b.get("pubtime"),
            "replynum": b.get("commentNum") if b.get("commentNum") is not None else b.get("replynum"),
            "readnum": b.get("readnum"),
            "abstract": b.get("abstract"),
            "cate": b.get("cate"),
        })
    return _dumps({"total": d.get("totalNum"), "pos": int(pos), "items": items})


@mcp.tool()
def get_blog(blogid: str, format: str = "text") -> str:
    """读取单篇日志的完整内容

    Args:
        blogid: 日志 ID（list_blogs 返回的 blogid）
        format: text（纯文本，默认）或 html（原始 HTML）
    """
    text = _fetch(BLOGS_INFO_URL, {
        "uin": _owner_uin(), "blogid": str(blogid),
        "styledm": "qzonestyle.gtimg.cn", "imgdm": "qzs.qq.com",
        "bdm": "b.qzone.qq.com", "mode": "2", "numperpage": "50",
        "timestamp": int(time.time()), "dprefix": "",
        "inCharset": "gb2312", "outCharset": "gb2312", "ref": "qzone",
        "page": "1",
        "refererurl": "https://qzs.qq.com/qzone/app/blog/v6/bloglist.html#nojump=1&page=1&catalog=list",
    }, charset="gbk")
    # 元数据在 var g_oBlogData = {...} 里，正文在 #blogDetailDiv
    meta = {}
    m = re.search(r"var g_oBlogData\s*=\s*(\{[\s\S]+?\});", text)
    if m:
        try:
            meta = (json.loads(m.group(1)) or {}).get("data") or {}
        except Exception:  # noqa: BLE001
            meta = {}
    content_html = _extract_div(text, "blogDetailDiv")
    if content_html is None:
        t = re.search(r"var g_oBlogContent\s*=\s+'([\s\S]+?/div>)';", text)
        content_html = _js_string_decode(t.group(1)) if t else text
    content = content_html if format == "html" else _html_to_text(content_html)
    pub = meta.get("pubtime")
    if isinstance(pub, (int, float)) and pub > 0:
        pub = time.strftime("%Y-%m-%d %H:%M", time.localtime(pub))
    return _dumps({
        "blogid": str(blogid),
        "title": meta.get("title"),
        "pubtime": pub,
        "replynum": meta.get("replynum"),
        "format": format,
        "content": content,
    })


@mcp.tool()
def list_albums(pos: int = 0, num: int = 30, route: int = 102) -> str:
    """读取相册列表

    Args:
        pos: 从第几个相册开始（分页），默认 0
        num: 每页个数，默认 30，最大 50
        route: 相册路由号，默认 102（一般不用改）
    """
    num = max(1, min(int(num), 50))
    data = _get_json(ALBUM_LIST_URL, {
        "g_tk": _gtk(), "callback": "shine0_Callback", "t": _photo_ts(),
        "hostUin": _owner_uin(), "uin": _owner_uin(), "appid": 4,
        "inCharset": "utf-8", "outCharset": "utf-8", "source": "qzone",
        "plat": "qzone", "format": "jsonp", "notice": 0, "filter": 1,
        "handset": 4, "needUserInfo": 1, "idcNum": int(route), "mode": 2,
        "sortOrder": "2", "pageStart": int(pos), "pageNum": num,
        "callbackFun": "shine0", "_": int(time.time() * 1000),
    })
    d = data.get("data") or {}
    return _dumps({
        "total": d.get("albumsInUser"),
        "pos": int(pos),
        "items": [_trim_album(a) for a in (d.get("albumList") or [])],
    })


@mcp.tool()
def list_photos(album_id: str, pos: int = 0, num: int = 30, route: int = 102) -> str:
    """读取某个相册里的相片列表（含原图/高清/普通图地址）

    Args:
        album_id: 相册 ID（list_albums 返回的 id）
        pos: 从第几张开始（分页），默认 0
        num: 每页张数，默认 30，最大 60
        route: 相册路由号，默认 102（一般不用改）
    """
    num = max(1, min(int(num), 60))
    data = _get_json(IMAGES_LIST_URL, {
        "g_tk": _gtk(), "callback": "shine0_Callback", "t": _photo_ts(),
        "mode": 0, "idcNum": int(route), "hostUin": _owner_uin(),
        "topicId": str(album_id), "noTopic": 0, "uin": _owner_uin(),
        "pageStart": int(pos), "pageNum": num, "skipCmtCount": 0,
        "singleurl": 1, "batchId": "", "notice": 0, "appid": 4,
        "inCharset": "utf-8", "outCharset": "utf-8", "source": "qzone",
        "plat": "qzone", "outstyle": "json", "format": "jsonp",
        "json_esc": 1, "callbackFun": "shine0", "_": int(time.time() * 1000),
    })
    d = data.get("data") or {}
    return _dumps({
        "total": d.get("totalInAlbum"),
        "pos": int(pos),
        "album": _trim_album(d.get("topic") or {}),
        "items": [_trim_photo(p) for p in (d.get("photoList") or [])],
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")
