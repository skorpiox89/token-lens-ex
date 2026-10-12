#!/usr/bin/env python3
"""把已插入 drawio 的文档里的 mermaid 块删掉（先备份到本地）。

用法：
    strip_mermaid.py [--dry-run]
备份：export/drawio/mermaid_backup/<chartId>_<docId>.md
"""
import argparse
import json
import os
import re
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "export/drawio")
BACKUP = os.path.join(OUT_DIR, "mermaid_backup")
SIYUAN = os.environ.get("SIYUAN_URL", "http://127.0.0.1:6806")
ACCESS_CODE = "11080703love!@#"
OPS = {"62f617b3f346fb0731874954": {"docId": "20261010165158-2g5ii5o", "hpath": "/001.工作/007.天翼云/ops-job-supervisor"}}


def login():
    req = urllib.request.Request(
        SIYUAN + "/api/system/loginAuth",
        data=json.dumps({"authCode": ACCESS_CODE}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        cookie = resp.headers.get("Set-Cookie", "")
    return re.search(r"siyuan=([^;]+)", cookie).group(1)


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    docs = {}
    for g in ("A", "B", "C"):
        f = os.path.join(OUT_DIR, "state_%s.json" % g)
        if not os.path.exists(f):
            continue
        for cid, v in json.load(open(f, encoding="utf-8")).items():
            if v.get("inserted"):
                docs[cid] = v
    docs.update(OPS)

    cookie = login()
    os.makedirs(BACKUP, exist_ok=True)
    total = removed = 0
    for cid, v in docs.items():
        doc_id, hpath = v["docId"], v.get("hpath", "")
        rows = sql(
            f"SELECT id, markdown FROM blocks WHERE root_id='{doc_id}' "
            "AND markdown LIKE '%```mermaid%'",
            cookie,
        )
        if not rows:
            continue
        total += len(rows)
        name = os.path.basename(hpath) or doc_id
        path = os.path.join(BACKUP, f"{cid}_{name}.md")
        body = "\n\n---\n\n".join(r["markdown"] for r in rows)
        if args.dry_run:
            print(f"[dry] {hpath}: 将删除 {len(rows)} 个 mermaid 块 -> {path}")
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body + "\n")
        for r in rows:
            res = post("/api/block/deleteBlock", {"id": r["id"]}, cookie)
            if res.get("code") != 0:
                print(f"✗ {hpath}: 删除块 {r['id']} 失败 {res.get('msg')}")
            else:
                removed += 1
        left = sql(
            f"SELECT COUNT(*) c FROM blocks WHERE root_id='{doc_id}' AND markdown LIKE '%```mermaid%'",
            cookie,
        )[0]["c"]
        frames = sql(f"SELECT COUNT(*) c FROM blocks WHERE root_id='{doc_id}' AND type='iframe'", cookie)[0]["c"]
        print(f"{'✓' if left == 0 else '✗'} {hpath}  mermaid={left}  iframe={frames}")

    print(f"\n{'[dry] ' if args.dry_run else ''}文档 {len(docs)} 篇，发现 mermaid 块 {total} 个，已删 {removed} 个")
    print("备份目录：", BACKUP)


if __name__ == "__main__":
    main()
