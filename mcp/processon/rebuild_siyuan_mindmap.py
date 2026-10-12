#!/usr/bin/env python3
"""ProcessOn 思维导图 → 思源原生列表（插件「大纲导图」渲染）

对每个文档：保留新内容（来源引用 + 原生列表），清掉旧的 markmap/代码块内容，
并把列表容器块属性 custom-mindmap 设为 logic。
"""
import json, re, sys, time, urllib.request

SIYUAN = "http://127.0.0.1:6806"
TOKEN = json.load(open('/root/code/si-yuan/workspace/conf/conf.json'))['api']['token']
MD_DIR = '/tmp/pm'


def api(path, payload=None):
    req = urllib.request.Request(
        SIYUAN + path, method='POST' if payload is not None else 'GET',
        data=json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
        headers={'Authorization': 'Token ' + TOKEN, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def sql(stmt):
    r = api('/api/query/sql', {'stmt': stmt})
    if r.get('code') != 0:
        raise RuntimeError(f"SQL failed: {r}")
    return r['data']


def children(block_id):
    return sql("SELECT id, type, created, content, substr(ial,1,120) AS ial FROM blocks "
               f"WHERE parent_id = '{block_id}' ORDER BY sort, created")


MAP = {
 "604ace3c7d9c08389fd9c7af": "20261010165201-hl82g79",
 "5f1a97921e08533a6283cf8c": "20261010165202-8codu6r",
 "6012b3dbf346fb1b2a6336d9": "20261010165203-go6ueat",
 "5cce47d1e4b09b16ffd1082c": "20261010165205-ge9g99n",
 "5a5eea20e4b0a447b9aaa414": "20261010165206-l89wk03",
 "5ba091a5e4b08faf8c59a581": "20261010165211-8pvc0j4",
 "5b31ed86e4b048764d85a329": "20261010165212-mp55fks",
 "59feab1de4b0f84f8976f9c1": "20261010165213-ycm2ptz",
 "5a8fb512e4b0615ac05cb0b4": "20261010165225-2ep512j",
 "6146240ce401fd7861a664cb": "20261010165215-w8jlt9p",
 "609ea348f346fb1df4167b46": "20261010165216-yx9h8wr",
 "5baf41a3e4b075b9fe5d71b4": "20261010165217-lkvt9fh",
 "5d148769e4b0b96168c57f28": "20261010165217-c7tlnp0",
 "5cd8bb41e4b0406c6415a3b8": "20261010165218-0cfux9r",
 "5ce7b38de4b0fea7c10a4c47": "20261010165219-uvg93q1",
 "5ce65f25e4b022becb425b77": "20261010165220-ryzt5v6",
 "5c12874ae4b0ed122da5a7ae": "20261010165221-1jnr6eu",
 "5be9aac2e4b01c7467b6d0bc": "20261010165222-nnuu8wj",
 "5b7cdce0e4b05728c455ff67": "20261010165223-ofut0q6",
 "5b519245e4b067df59e3313c": "20261010165224-n3fw4wo",
 "59f841e3e4b0d53d9792c6f9": "20261010165227-djls5s4",
 "5a7ffcbce4b0615ac05660c1": "20261010165228-6163l3i",
 "5eea27c75653bb2925a12c64": "20261010165237-xu27llg",
 "5ef9c902f346fb1ae5846d5f": "20261010165238-ducjfd8",
 "5d6e9130e4b04c14c4d6ea43": "20261010165241-jxm7v6q",
 "5da9cd09e4b002a6448c7c23": "20261010165245-jrcqtc4",
 "614345b75653bb4327de6173": "20261010165246-p800e17",
 "5de0042be4b00e6d900d5a20": "20261010165248-u4fmrht",
 "5b5f05b0e4b08d3622965b5b": "20261010165249-d4gtap8",
}

LEAD_ESC = set('#*+>~')


def convert_outline(md):
    idx = md.find('## 大纲')
    if idx < 0:
        raise RuntimeError('no outline section')
    lines = [l for l in md[idx + len('## 大纲'):].splitlines() if l.strip()]
    out = []
    for l in lines:
        s = l.strip()
        if not s.startswith('- '):
            raise RuntimeError(f'unexpected outline line: {l!r}')
        text = s[2:]
        level = (len(l) - len(l.lstrip(' '))) // 2
        if re.match(r'^\d+\.\s', text):
            text = re.sub(r'^(\d+)\.', r'\1\\.', text, count=1)
        if text[:1] in LEAD_ESC:
            text = '\\' + text
        text = text.replace('<', r'\<').replace('>', r'\>')
        out.append('    ' * level + '- ' + text)
    return out


def top(block_id):
    return children(block_id)


def rebuild(cid, doc, dry=False):
    md = open(f'{MD_DIR}/{cid}.md', encoding='utf-8').read()
    outline = convert_outline(md)
    title = md.splitlines()[0].lstrip('# ').strip()
    if dry:
        print(f"--- {cid} {title} nodes={len(outline)}")
        print('\n'.join(outline[:12]))
        return
    rows0 = top(doc)
    if rows0 and all((r.get('created') or '') >= '20261011' for r in rows0) \
            and any(r['type'] == 'l' and 'custom-mindmap' in (r.get('ial') or '') for r in rows0):
        print(f"SKIP {cid} already rebuilt")
        return
    # 1) 收集旧块（文档直属子块 + 标题子块，删除父块时会级联，标题子块会被提拔所以也要收）
    olds = set()
    for r in top(doc):
        olds.add(r['id'])
        for c in top(r['id']):
            olds.add(c['id'])
    # 2) 先追加新内容（此时文档非空，避免打开的编辑器自动插入空段落）
    quote = (f"> 来源：[ProcessOn 原图](https://www.processon.com/mindmap/{cid})"
             f" · 归档于 2026-10-10")
    full = quote + "\n\n" + "\n".join(outline)
    r = api('/api/block/appendBlock', {'dataType': 'markdown', 'data': full, 'parentID': doc})
    if r.get('code') != 0:
        raise RuntimeError(f'append failed: {r}')
    # 3) 删除旧块
    for bid in olds:
        api('/api/block/deleteBlock', {'id': bid})
    # 4) 清理残留（旧块被提拔 / 编辑器补的空段落），最多 30 轮
    listid = None
    for _ in range(30):
        time.sleep(0.6)
        rows = top(doc)
        for r in rows:
            created = r.get('created') or ''
            is_old = created < '20261011'
            is_empty_p = r['type'] == 'p' and not (r.get('content') or '').strip()
            if is_old or is_empty_p:
                api('/api/block/deleteBlock', {'id': r['id']})
        rows = [r for r in top(doc) if r['type'] == 'l' and (r.get('created') or '') >= '20261012']
        if rows:
            listid = rows[0]['id']
            break
    if not listid:
        raise RuntimeError('new list container not found')
    r = api('/api/attr/setBlockAttrs', {'id': listid, 'attrs': {'custom-mindmap': 'logic'}})
    if r.get('code') != 0:
        raise RuntimeError(f'setattr failed: {r}')
    n = sql(f"SELECT COUNT(*) AS n FROM blocks WHERE parent_id = '{listid}'")
    print(f"OK {cid} {title!r} nodes={len(outline)} list={listid} top_items={n[0]['n']}")


if __name__ == '__main__':
    if '--dry' in sys.argv:
        for cid in MAP:
            rebuild(cid, MAP[cid], dry=True)
    elif '--only' in sys.argv:
        cid = sys.argv[sys.argv.index('--only') + 1]
        rebuild(cid, MAP[cid])
    else:
        fail = []
        for cid, doc in MAP.items():
            try:
                rebuild(cid, doc)
            except Exception as e:
                fail.append((cid, str(e)))
                print(f"FAIL {cid}: {e}")
        print(f"\n完成 {len(MAP)-len(fail)}/{len(MAP)}")
        for cid, e in fail:
            print("  FAIL", cid, e)
