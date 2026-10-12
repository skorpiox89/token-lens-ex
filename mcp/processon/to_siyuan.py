#!/usr/bin/env python3
"""把 ProcessOn 图表批量导入思源笔记（镜像原始文件夹结构）。

每篇文档内容：
    > 来源：[ProcessOn 原图](...) · 归档于 <时间>
    flow 类 → ```mermaid 代码块（思源直接渲染）
    mind 类 → Markdown 嵌套大纲

幂等：目标 hpath 已存在则跳过（重复执行不会产生副本）。
用法：
    ./venv/bin/python to_siyuan.py --notebook "ProcessOn 归档"
    ./venv/bin/python to_siyuan.py --notebook <notebookId> --dry-run
"""

import argparse
import json
import os
import re
import time
import urllib.request

import server

SIYUAN_URL = os.environ.get("SIYUAN_URL", "http://127.0.0.1:6806")
# 凭证不写进代码（本脚本可能入库）：从环境变量或同目录 siyuan.json 读取
SIYUAN_TOKEN = os.environ.get("SIYUAN_TOKEN", "")
OUT_MAP = os.path.join(server.EXPORT_DIR, "archive", "siyuan_map.json")

# hpath 不允许的字符（斜杠是路径分隔符，必须替换）
_BAD_SEG = re.compile(r'[\\/:*?"<>|#^\[\]\r\n\t]+')

# 同目录重名时的类型后缀（如「面试框架」下有流程图与思维导图各一张）
_TYPE_SUFFIX = {
    "flow": "流程图", "flowbase": "流程图", "mind": "思维导图",
    "mind_free": "思维导图", "mind_org": "组织导图", "outline": "大纲",
    "uml": "UML图", "ui": "UI图", "network": "拓扑图",
}


def sy(path: str, payload: dict) -> dict:
    global SIYUAN_TOKEN
    if not SIYUAN_TOKEN:
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "siyuan.json")
        if os.path.exists(cfg_path):
            SIYUAN_TOKEN = (json.load(open(cfg_path, encoding="utf-8")) or {}).get("token", "")
    if not SIYUAN_TOKEN:
        raise SystemExit("请设置 SIYUAN_TOKEN 环境变量，或写入 siyuan.json（{\"token\": \"...\"}）")
    req = urllib.request.Request(
        SIYUAN_URL + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Token " + SIYUAN_TOKEN,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def clean_seg(text) -> str:
    s = _BAD_SEG.sub("_", str(text or "").strip())
    return s[:80].strip("_ .") or "未命名"


def disambig(title: str, item: dict) -> str:
    """同一目录下重名：加类型后缀（如「面试框架（思维导图）」）。"""
    cat = str(item.get("category") or "").lower()
    return f"{title}（{_TYPE_SUFFIX.get(cat, cat or '副本')}）"


def resolve_notebook(name: str) -> str:
    """按 id 或名称解析笔记本；不存在则创建。"""
    nbs = (sy("/api/notebook/lsNotebooks", {}).get("data") or {}).get("notebooks") or []
    for nb in nbs:
        if nb.get("id") == name or nb.get("name") == name:
            return nb["id"]
    created = sy("/api/notebook/createNotebook", {"name": name})
    nb_id = ((created.get("data") or {}).get("notebook") or {}).get("id")
    if not nb_id:
        raise SystemExit(f"创建笔记本失败：{created}")
    return nb_id


def existing_hpaths(nb_id: str) -> set:
    rows = sy("/api/query/sql", {
        "stmt": f"SELECT hpath FROM blocks WHERE box = '{nb_id}' AND type = 'd'",
    })
    return {r.get("hpath", "") for r in rows.get("data") or []}


def collect(folder_id: str = "root", max_depth: int = 6):
    """递归收集 (folders_path, chart_item)。"""
    out, seen = [], set()

    def walk(fid, path, depth):
        if fid in seen or depth > max_depth:
            return
        seen.add(fid)
        data = server._list_files_raw(fid, 1, 200)
        for f in data.get("folders") or []:
            it = server._norm_item(f, "folder")
            walk(it["folderId"], path + [clean_seg(it["title"] or it["folderId"])], depth + 1)
        for c in data.get("charts") or []:
            out.append((list(path), server._norm_item(c, "chart")))

    walk(folder_id, [], 0)
    return out


def build_markdown(chart_id: str, info: dict) -> tuple:
    conv = server._convert_chart(chart_id, info["meta"], info)
    url = server._chart_url(chart_id, str(info["meta"].get("category", "")))
    parts = [f"> 来源：[ProcessOn 原图]({url}) · 归档于 {time.strftime('%Y-%m-%d')}"]
    if conv["format"] == "mermaid" and conv["body"]:
        parts.append(f"```mermaid\n{conv['body']}\n```")
    elif conv["body"]:
        parts.append(conv["body"])
    # 思维导图：除了可渲染的 mindmap，再附一份大纲文本（方便阅读/搜索/复制）
    if conv.get("outline"):
        parts.append("## 大纲\n\n" + conv["outline"])
    return "\n\n".join(parts) + "\n", conv


def main() -> int:
    ap = argparse.ArgumentParser(description="ProcessOn 图表导入思源")
    ap.add_argument("--notebook", default="ProcessOn 归档", help="笔记本名称或 id")
    ap.add_argument("--folder", default="root", help="起始 folderId")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不写入")
    args = ap.parse_args()

    nb_id = resolve_notebook(args.notebook)
    print(f"笔记本：{args.notebook} ({nb_id})")
    have = existing_hpaths(nb_id)
    print(f"已有文档 {len(have)} 篇")

    items = collect(args.folder)
    print(f"待处理图表 {len(items)} 张\n")

    mapping, created, skipped, failed = {}, 0, 0, 0
    # 已存在 hpath → 所属 chartId（来自上次导入映射，且该文档当前确实存在）：
    # 用来区分「就是我自己上次导的（跳过）」与「同名但归属别的图（消歧义）」
    old_map = {}
    if os.path.exists(OUT_MAP):
        try:
            old_map = json.load(open(OUT_MAP, encoding="utf-8")) or {}
        except Exception:
            old_map = {}
    owner = {v["hpath"]: cid for cid, v in old_map.items()
             if isinstance(v, dict) and v.get("hpath") in have}

    for path, item in items:
        cid = item["chartId"]
        title = clean_seg(item["title"] or cid)
        base = "/" + "/".join([*path, title])
        # 依次尝试：原名 → 类型后缀 → chartId 尾缀；遇到自己的文档则跳过，
        # 被别人占用则换下一个候选名
        hpath, mine = None, None
        for cand in (base,
                     "/" + "/".join([*path, disambig(title, item)]),
                     "/" + "/".join([*path, f"{title}（{cid[-6:]}）"])):
            if cand not in have:
                hpath = cand
                break
            if owner.get(cand) == cid:
                mine = cand
                break
        if hpath is None:
            skipped += 1
            mapping[cid] = {"hpath": mine or base, "skipped": True}
            continue
        if args.dry_run:
            print(f"  [计划] {hpath}")
            have.add(hpath)      # 干跑也记录，才能看出重名改写
            owner[hpath] = cid
            continue
        try:
            info = server._chart_def_raw(cid)
            md, conv = build_markdown(cid, info)
            res = sy("/api/filetree/createDocWithMd",
                     {"notebook": nb_id, "path": hpath, "markdown": md})
            if res.get("code") != 0:
                raise RuntimeError(res.get("msg") or res)
            doc_id = res.get("data")
            mapping[cid] = {"hpath": hpath, "docId": doc_id,
                            "title": item["title"], "format": conv["format"],
                            "url": server._chart_url(cid, str(item["category"]))}
            have.add(hpath)
            owner[hpath] = cid
            created += 1
            print(f"  ✓ {hpath}  [{conv['format']}]")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ✗ {hpath}: {exc}")

    if not args.dry_run:
        os.makedirs(os.path.dirname(OUT_MAP), exist_ok=True)
        with open(OUT_MAP, "w", encoding="utf-8") as fh:
            json.dump(mapping, fh, ensure_ascii=False, indent=2)
    print(f"\n完成：新增 {created} / 跳过 {skipped} / 失败 {failed}，共 {len(items)}")
    if not args.dry_run:
        print(f"映射表：{OUT_MAP}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
