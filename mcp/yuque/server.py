"""
语雀 MCP Server（本地 stdio 版，双认证模式）

两种认证方式（按优先级自动选择）：
    1. YUQUE_TOKEN     —— 官方 OpenAPI 令牌（需超级会员），走 /api/v2 系列
    2. YUQUE_COOKIE    —— 浏览器登录 cookie（无需任何会员），走网页端 /api 系列

Cookie 模式原理（本文件核心学习点）：
    - 语雀网页版内部接口（/api/mine、/api/docs 等）只认登录态 cookie，
      不校验 OpenAPI 令牌，因此普通用户也可以读写自己的知识库。
    - 需要两个 cookie：_yuque_session（会话凭证）+ yuque_ctoken（CSRF 令牌）。
    - 获取方法：浏览器 F12 → Network → 刷新语雀页面 → 点任意请求 →
      Request Headers 里整段复制 "Cookie: ..." 的值。
    - 注意：网页端接口是未公开的内部接口，语雀改版后可能需要适配；
      cookie 有效期约 2 周，过期后需重新复制。

运行前提：
    1. pip install "mcp>=1.2.0,<2"   （mcp 2.x 移除了 FastMCP，必须锁 1.x）
    2. 设置 YUQUE_TOKEN 或 YUQUE_COOKIE 环境变量
    3. python server.py              （stdio 传输，供 MCP 客户端调用）
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

V2_BASE = "https://www.yuque.com/api/v2"   # 官方 OpenAPI（token 模式）
WEB_BASE = "https://www.yuque.com/api"     # 网页端内部接口（cookie 模式）

mcp = FastMCP("yuque")


# ---------- 内部工具函数（不对外暴露） ----------

class _Mode:
    """认证模式：token（OpenAPI）或 cookie（网页端接口）"""

    def __init__(self, name: str, base: str, cookie: str = "", ctoken: str = "",
                 referer: str = ""):
        self.name = name
        self.base = base
        self.cookie = cookie
        self.ctoken = ctoken
        self.referer = referer


def _resolve_mode() -> _Mode:
    """按优先级选择认证模式：token 优先，其次 cookie"""
    token = os.environ.get("YUQUE_TOKEN") or os.environ.get("YUQUE_PERSONAL_TOKEN")
    if token:
        return _Mode("token", V2_BASE)

    cookie = os.environ.get("YUQUE_COOKIE", "").strip()
    if cookie:
        # 从整段 cookie 里提取 CSRF 令牌（写操作需要）
        m = re.search(r"yuque_ctoken=([^;]+)", cookie)
        return _Mode("cookie", WEB_BASE, cookie, m.group(1) if m else "",
                     referer=f"https://www.yuque.com/{os.environ.get('YUQUE_LOGIN', '')}")

    raise RuntimeError(
        "未检测到语雀凭证。两种方式任选其一：\n"
        "  1) YUQUE_TOKEN（官方令牌，需超级会员）\n"
        "  2) YUQUE_COOKIE（浏览器 cookie，免费）——F12 → Network → 复制请求头里 "
        "整段 'Cookie: ...'，需包含 _yuque_session 和 yuque_ctoken"
    )


def _request(mode: _Mode, method: str, path: str, params: dict | None = None,
             payload: dict | None = None) -> dict:
    """统一请求封装。params 走 query string，payload 走 JSON 请求体（两种模式都是 JSON）"""
    url = f"{mode.base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    data = None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Referer": "https://www.yuque.com/",
    }
    if mode.name == "token":
        headers["X-Auth-Token"] = os.environ["YUQUE_TOKEN"]
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
    else:
        headers["Cookie"] = mode.cookie
        if payload is not None:
            # 网页端写接口要求：JSON 体 + CSRF 头 + XHR 标识 + Referer
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
            headers["X-Requested-With"] = "XMLHttpRequest"
            if mode.ctoken:
                headers["X-CSRF-Token"] = mode.ctoken
            headers["Referer"] = mode.referer or headers["Referer"]

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    # 幂等请求（GET/PUT/DELETE）遇超时/网络抖动重试一次；POST 不重试，避免重复创建
    max_attempts = 2 if method.upper() in ("GET", "PUT", "DELETE", "HEAD") else 1
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"语雀接口返回错误 {e.code} ({mode.name} 模式): {detail[:300]}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt + 1 < max_attempts:
                time.sleep(1)
                continue
            raise RuntimeError(f"无法连接语雀: {getattr(e, 'reason', e)}") from e


def _current_user(mode: _Mode) -> dict:
    """获取当前登录用户信息（两种模式各自的取法）"""
    if mode.name == "token":
        return _request(mode, "GET", "/user")
    data = _request(mode, "GET", "/mine")
    return data.get("data", data) if isinstance(data, dict) else data


def _books(mode: _Mode) -> list[dict]:
    """获取当前用户的所有知识库（统一结构：id/name/slug/namespace）"""
    if mode.name == "token":
        user = _current_user(mode)
        login = user.get("login", "")
        repos = _request(mode, "GET", f"/users/{login}/repos")
        return [
            {"id": r.get("id"), "name": r.get("name"), "slug": r.get("slug"),
             "namespace": r.get("namespace", ""), "type": r.get("type", "book")}
            for r in repos
        ]
    data = _request(mode, "GET", "/mine/books")
    books = data.get("data", data) if isinstance(data, dict) else data
    return [
        {"id": b.get("id"), "name": b.get("name"), "slug": b.get("slug"),
         "namespace": f"{b.get('user_id', '')}/{b.get('slug', '')}", "type": b.get("type", "book")}
        for b in books
    ]


def _resolve_book(mode: _Mode, book: str) -> dict:
    """把用户传入的知识库（namespace / slug / id / 名称）解析成 {id, name, slug, namespace}"""
    for b in _books(mode):
        if book in (b["namespace"], b["slug"], str(b["id"]), b["name"]):
            return b
    raise RuntimeError(f"找不到知识库: {book}（可先调用 list_repos 查看可用的 namespace）")


def _find_doc(mode: _Mode, book_id: int, doc: str) -> dict:
    """定位文档：先按传入的 slug/id 精确查，找不到就在书里按标题匹配"""
    params = {"book_id": book_id}
    if mode.name == "cookie":
        params["mode"] = "markdown"          # 网页端接口：要求返回 markdown 正文
        params["merge_dynamic_data"] = "false"
    try:
        data = _request(mode, "GET", f"/docs/{doc}", params=params)
        return data.get("data", data)
    except RuntimeError:
        docs = _request(mode, "GET", "/docs", params={"book_id": book_id})
        for d in docs.get("data", docs):
            if doc in (str(d.get("id")), d.get("slug"), d.get("title")):
                # 列表项不含正文；按 id 再查一次详情，否则读写都会拿到空 body
                detail = _request(mode, "GET", f"/docs/{d.get('id')}", params=params)
                return detail.get("data", detail)
        raise RuntimeError(f"在知识库 {book_id} 中找不到文档: {doc}")


# ---------- MCP 工具（下面每个函数都会成为 AI 可调用的工具） ----------

@mcp.tool()
def get_user() -> str:
    """获取当前语雀账号信息，用于确认凭证（token/cookie）是否有效"""
    mode = _resolve_mode()
    user = _current_user(mode)
    return json.dumps(user, ensure_ascii=False, indent=2)


@mcp.tool()
def list_repos() -> str:
    """列出当前账号名下的所有知识库（含 id/name/slug/namespace）"""
    mode = _resolve_mode()
    return json.dumps(_books(mode), ensure_ascii=False, indent=2)


@mcp.tool()
def list_docs(book: str) -> str:
    """列出知识库下的所有文档

    Args:
        book: 知识库标识（list_repos 返回的 namespace、slug、id 或名称均可）
    """
    mode = _resolve_mode()
    b = _resolve_book(mode, book)
    data = _request(mode, "GET", "/docs", params={"book_id": b["id"]})
    docs = data.get("data", data)
    summary = [
        {"id": d.get("id"), "title": d.get("title"), "slug": d.get("slug"),
         "status": d.get("status")}
        for d in docs
    ]
    return json.dumps(summary, ensure_ascii=False, indent=2)


@mcp.tool()
def create_doc(book: str, title: str, body_md: str, slug: str = "") -> str:
    """在指定知识库中创建一篇新文档（正文为 Markdown）

    Args:
        book: 知识库标识（list_repos 返回的 namespace、slug、id 或名称均可）
        title: 文档标题
        body_md: 文档正文（Markdown 格式）
        slug: 文档 URL 别名，留空则自动生成
    """
    mode = _resolve_mode()
    b = _resolve_book(mode, book)
    if mode.name == "token":
        payload = {"title": title, "body": body_md, "format": "markdown"}
        if slug:
            payload["slug"] = slug
        data = _request(mode, "POST", f"/repos/{b['namespace']}/docs", payload=payload)
    else:
        # 网页端创建文档：POST /api/docs，JSON 体（参考 yuque-cookie-plugin）
        login = _current_user(mode).get("login", "")
        mode.referer = f"https://www.yuque.com/{login}/{b['slug']}"
        payload = {"book_id": b["id"], "title": title, "format": "markdown",
                   "body": body_md, "body_draft": body_md, "public": 0}
        if slug:
            payload["slug"] = slug
        resp = _request(mode, "POST", "/docs", payload=payload)
        data = resp.get("data", resp)
        data.setdefault("url", f"https://www.yuque.com/{login}/{b['slug']}/{data.get('slug', '')}")
    return json.dumps(
        {"id": data.get("id"), "title": data.get("title"), "slug": data.get("slug"),
         "url": data.get("url"), "message": "创建成功"},
        ensure_ascii=False, indent=2,
    )


@mcp.tool()
def get_doc(book: str, doc: str) -> str:
    """获取知识库中某篇文档的详细内容

    Args:
        book: 知识库标识（namespace、slug、id 或名称均可）
        doc: 文档的 slug、id 或标题
    """
    mode = _resolve_mode()
    b = _resolve_book(mode, book)
    d = _find_doc(mode, b["id"], doc)
    # 网页端接口把正文放在 sourcecode（markdown 模式），OpenAPI 放 body
    body = d.get("body") or d.get("sourcecode") or ""
    url = d.get("url")
    if not url and mode.name == "cookie":
        login = _current_user(mode).get("login", "")
        url = f"https://www.yuque.com/{login}/{b['slug']}/{d.get('slug', '')}"
    return json.dumps(
        {"id": d.get("id"), "title": d.get("title"), "slug": d.get("slug"),
         "url": url, "body": body},
        ensure_ascii=False, indent=2,
    )


@mcp.tool()
def update_doc(book: str, doc: str, title: str = "", body_md: str = "") -> str:
    """更新知识库中已有文档的标题或正文

    Args:
        book: 知识库标识（namespace、slug、id 或名称均可）
        doc: 要更新的文档的 slug、id 或标题
        title: 新标题（留空表示不修改）
        body_md: 新正文（Markdown 格式，留空表示不修改）
    """
    mode = _resolve_mode()
    b = _resolve_book(mode, book)
    d = _find_doc(mode, b["id"], doc)
    if mode.name == "token":
        payload = {"title": d.get("title", ""), "body": d.get("body", ""), "format": "markdown"}
        if title:
            payload["title"] = title
        if body_md:
            payload["body"] = body_md
        data = _request(mode, "PUT", f"/repos/{b['namespace']}/docs/{d.get('slug')}",
                        payload=payload)
    else:
        # 网页端更新：PUT /api/docs/{id}，直接提交 markdown 正文。
        # 实测：/docs/{id}/content 接口只接受 lake 系列格式（还需 body_asl/save_type/
        # draft_version），markdown 文档无法用它保存；而 PUT /api/docs/{id} 对
        # markdown 文档一步完成保存+发布，无需 /publish。
        login = _current_user(mode).get("login", "")
        mode.referer = f"https://www.yuque.com/{login}/{b['slug']}"
        old_body = d.get("body") or d.get("sourcecode") or ""
        payload = {"format": "markdown",
                   "body": body_md if body_md else old_body,
                   "body_draft": body_md if body_md else old_body}
        if title:
            payload["title"] = title
        resp = _request(mode, "PUT", f"/docs/{d.get('id')}", payload=payload)
        data = resp.get("data", resp)
        data.setdefault("url", f"https://www.yuque.com/{login}/{b['slug']}/{d.get('slug', '')}")
    return json.dumps(
        {"id": data.get("id"), "title": data.get("title"), "slug": data.get("slug"),
         "url": data.get("url"), "message": "更新成功"},
        ensure_ascii=False, indent=2,
    )


if __name__ == "__main__":
    # stdio 传输：MCP 客户端（如 ZCode）通过标准输入输出与这个进程通信
    mcp.run(transport="stdio")
