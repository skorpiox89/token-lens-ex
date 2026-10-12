#!/usr/bin/env python3
"""批次：ProcessOn 图表 -> .drawio 文件 + 在思源对应文档插入 drawio iframe 块。

用法：
    drawio_batch.py --ids id1,id2,... [--dry-run] [--force]
    drawio_batch.py --group A            # 内置 A 组清单
状态（断点/幂等）：export/drawio/state_<group>.json
"""
import argparse
import json
import os
import re
import shutil
import string
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import processon_to_drawio as p2d  # noqa: E402

SIYUAN = os.environ.get("SIYUAN_URL", "http://127.0.0.1:6806")
ACCESS_CODE = "11080703love!@#"
PETAL_DIR = "/root/code/si-yuan/workspace/data/storage/petal/siyuan-drawio-plugin"
PETAL_UID = 1000
DEF_DIR = os.path.join(BASE, "export/archive/def")
MAP_FILE = os.path.join(BASE, "export/archive/siyuan_map.json")
OUT_DIR = os.path.join(BASE, "export/drawio")

A_GROUP = """62f0b8b01e08531524c76291 6315afe11e0853187c13935a 6315be160e3e74743f4f19cb 6315b3715653bb40f8373fce
632192847d9c081f94d0fff8 63198eab63768972fee723f2 5f1a8b9ee0b34d54dac87f72 5f6c6241f346fb166d09ee12
62578a32e0b34d0a5a414fae 5b84b4ede4b0d4d65be97a79 6090ee877d9c084071a907a2 5ce53af2e4b031f153a20caa
5eea88a07d9c08442020518f 612d7d6a5653bb2d6d18b349 6115ef3ae401fd5eeb8c8a5f 5a1e1acde4b0add9c9f8dc1a
5a91a1a7e4b0874437cf0e4f 60f1ae51f346fb3f3413820f 59fa92ade4b06bed41cb648b 5a068f54e4b06bed41cf2bb8
59ded159e4b072e92907c5bd""".split()

DONE = {"62f617b3f346fb0731874954"}  # ops-job-supervisor，已手工完成

B_GROUP = """62be6fce07912925e5f84993 62be914607912925e5f8932c 62f1c7bcf346fb49413c0924 62f1c2b57d9c084f8034c36f
62c6485ff346fb075d390447 63195cd7e0b34d3313361642 5fdb85117d9c0855ea71d133 62151f5e0e3e74097fe40d30
5dd8dc8ce4b09e8b0b709449 59f9fcd4e4b0f84f8975c95f 5a0cfbf8e4b0d53d97996400 5f2a13671e08533a629b9875""".split()
GROUPS = {"A": A_GROUP, "B": B_GROUP}


# ── 思源 API ────────────────────────────────────────────────────────────
def sy_login():
    req = urllib.request.Request(
        SIYUAN + "/api/system/loginAuth",
        data=json.dumps({"authCode": ACCESS_CODE}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        cookie = resp.headers.get("Set-Cookie", "")
    m = re.search(r"siyuan=([^;]+)", cookie)
    if not m:
        raise SystemExit("思源登录失败：拿不到 siyuan cookie")
    return m.group(1)


def sy_post(path, payload, cookie):
    req = urllib.request.Request(
        SIYUAN + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Cookie": "siyuan=" + cookie},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def sql(stmt, cookie):
    res = sy_post("/api/query/sql", {"stmt": stmt}, cookie)
    if res.get("code") != 0:
        raise RuntimeError(res.get("msg"))
    return res.get("data") or []


# ── 工具 ────────────────────────────────────────────────────────────────
BAD = re.compile(r'[\\/:*?"<>|#^\[\]\r\n\t]+')


def clean_name(s):
    return BAD.sub("_", str(s)).strip() or "drawio"


def new_block_id():
    ts = time.strftime("%Y%m%d%H%M%S")
    return ts + "-" + "".join(random.choices(string.ascii_lowercase, k=7))


def find_def(cid):
    for f in os.listdir(DEF_DIR):
        if f.startswith(cid):
            return os.path.join(DEF_DIR, f)
    raise FileNotFoundError(cid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids")
    ap.add_argument("--group", default="A")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    ids = [s.strip() for s in args.ids.split(",")] if args.ids else GROUPS[args.group]
    smap = json.load(open(MAP_FILE, encoding="utf-8"))
    state_file = os.path.join(OUT_DIR, "state_%s.json" % args.group)
    state = json.load(open(state_file, encoding="utf-8")) if os.path.exists(state_file) else {}

    cookie = sy_login()
    os.makedirs(PETAL_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    for cid in ids:
        info = smap.get(cid) or {}
        hpath, doc_id = info.get("hpath"), info.get("docId")
        if not doc_id:
            print(f"✗ {cid} 无思源文档映射，跳过")
            continue
        if cid in DONE and not args.force:
            print(f"• {cid} 已手工完成，跳过")
            continue
        if cid in state and not args.force:
            print(f"• {cid} 已在状态中，跳过（{state[cid].get('file')}）")
            continue

        # 1) 生成 drawio
        def_obj = p2d.load_def(find_def(cid))
        title = clean_name(info.get("title") or hpath.rsplit("/", 1)[-1])
        block_id = new_block_id()
        fname = f"{title}-{block_id}.drawio"
        xml, nv, ne, (pw, ph) = p2d.convert(def_obj, name=title)
        height = max(420, min(900, round(950 * ph / pw)))

        # 2) 幂等检查：文档里是否已有 drawio iframe
        rows = sql(
            f"SELECT id FROM blocks WHERE root_id='{doc_id}' "
            "AND markdown LIKE '%siyuan-drawio-plugin%webapp%' LIMIT 1",
            cookie,
        )
        already = bool(rows)
        # 3) 找「来源」引用块，插到它后面（没有就插到文档最后）
        rows = sql(
            f"SELECT id FROM blocks WHERE root_id='{doc_id}' AND type='b' ORDER BY sort LIMIT 1",
            cookie,
        )
        prev = rows[0]["id"] if rows else None

        if args.dry_run:
            print(
                f"[dry] {cid} {title}: {nv}节点/{ne}连线 页面{pw}x{ph} 高{height}px "
                f"-> {fname}  doc={doc_id} prev={prev} 已有drawio={already}"
            )
            continue

        # 4) 落盘 + 插块
        dst = os.path.join(PETAL_DIR, fname)
        open(dst, "w", encoding="utf-8").write(xml)
        shutil.chown(dst, PETAL_UID, PETAL_UID)
        os.chmod(dst, 0o644)

        path = f"storage/petal/siyuan-drawio-plugin/{fname}"
        params = urllib.parse.urlencode([
            ("tags", "{}"), ("lightbox", "1"), ("highlight", "0000ff"),
            ("edit", "_blank"), ("layers", "1"),
            ("toolbar-config", json.dumps({"refreshBtn": {}}, separators=(",", ":"))),
            ("title", fname),
        ])
        src = f"/plugins/siyuan-drawio-plugin/webapp/?{params}#U{urllib.parse.quote(path, safe='')}"
        md = (
            f'<iframe frameborder="0" style="width:100%;height:{height}px;" src="{src}"></iframe>\n'
            f'{{: id="{block_id}" custom-data-assets="{path}" }}'
        )
        payload = {"dataType": "markdown", "data": md}
        if prev:
            payload["previousID"] = prev
        else:
            payload["parentID"] = doc_id
        res = sy_post("/api/block/insertBlock", payload, cookie)
        if res.get("code") != 0:
            print(f"✗ {cid} 插入失败：{res.get('msg')}")
            os.remove(dst)
            continue

        rows = []
        for _ in range(6):
            rows = sql(f"SELECT id,type FROM blocks WHERE id='{block_id}' LIMIT 1", cookie)
            if rows and rows[0]["type"] == "iframe":
                break
            time.sleep(0.4)
        ok = bool(rows) and rows[0]["type"] == "iframe"
        state[cid] = {
            "docId": doc_id, "hpath": hpath, "file": fname, "blockId": block_id,
            "nodes": nv, "edges": ne, "page": [pw, ph], "height": height,
            "inserted": ok, "ts": int(time.time()),
        }
        json.dump(state, open(state_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{'✓' if ok else '✗'} {cid} {title}  ({nv}节点/{ne}连线, {height}px) -> {fname}")

    print("状态：", state_file)


if __name__ == "__main__":
    main()
