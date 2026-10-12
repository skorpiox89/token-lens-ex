#!/usr/bin/env python3
"""全量导出 ProcessOn 图表（命令行版，不受 MCP 调用时长限制）。

用法：
    ./venv/bin/python export.py                     # 从 root 全量导出（默认最多 200 张）
    ./venv/bin/python export.py --folder <folderId>  # 指定文件夹
    ./venv/bin/python export.py --max 1000          # 提高单次上限
    ./venv/bin/python export.py --no-markdown       # 只存原始 JSON
    ./venv/bin/python export.py --out export/siyuan # 指定输出目录

输出：
    <out>/def/<chartId>_<title>.json   原始 elements JSON
    <out>/md/<chartId>_<title>.md      Mermaid / Markdown 大纲
    <out>/index.md                     目录索引
"""

import argparse
import json
import sys
import time

import server


def main() -> int:
    ap = argparse.ArgumentParser(description="导出 ProcessOn 图表")
    ap.add_argument("--folder", default="root", help="起始 folderId，默认 root")
    ap.add_argument("--max", type=int, default=200, help="最多导出张数，默认 200")
    ap.add_argument("--no-markdown", action="store_true", help="只导出原始 JSON")
    ap.add_argument("--out", default="", help="输出目录，默认 export/archive-<时间戳>")
    args = ap.parse_args()

    try:
        me = json.loads(server.check_auth())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        print("请先按 README 配置 token.txt（或 PROCESSON_ACCOUNT/PASSWORD）", file=sys.stderr)
        return 1
    if not me.get("ok"):
        print(f"FAIL: {me.get('error')}", file=sys.stderr)
        return 1
    print(f"登录账号：{me.get('nickName') or '?'} (userId={me.get('userId')})，"
          f"token 剩余 {me.get('daysLeft')} 天", file=sys.stderr)

    t0 = time.time()
    result = json.loads(server.export_folder(
        folder_id=args.folder,
        max_charts=max(1, args.max),
        with_markdown=not args.no_markdown,
        out_dir=args.out,
    ))
    if not result.get("ok"):
        print(f"FAIL: {result.get('error')}", file=sys.stderr)
        return 1
    print(f"完成：{result['exported']}/{result['attempted']} 张，"
          f"耗时 {time.time() - t0:.0f}s" +
          ("（已达上限，可能还有更多，请调大 --max 或分批）" if result.get("truncated") else ""),
          file=sys.stderr)
    for err in result.get("errors") or []:
        print(f"  ⚠️ {err['title']} ({err['chartId']}): {err['error']}", file=sys.stderr)
    print(f"输出目录：{result['outDir']}")
    print(f"索引：{result['index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
