#!/usr/bin/env python3
"""Dcard batch33 补入 Postgres，一帖一行，与 batch1-17 全量同格式同过滤。
口令只从环境变量 DBPASS 读，不写进文件；每板文件提交一次，已存在则不重复写。"""
import json, os, sys, glob
sys.path.insert(0, os.path.expanduser("~/workspace/dcard-full"))
from import_full_one_row import build_row

def main():
    batch = sys.argv[1] if len(sys.argv) > 1 else "33"
    pw = os.environ.get("DBPASS")
    if not pw:
        print("DBPASS 未设置", file=sys.stderr)
        return 2
    import psycopg
    conn = psycopg.connect(host="127.0.0.1", port=15432, dbname="postgres",
                           user="postgres", password=pw, connect_timeout=30)
    try:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM forum."dcard"')
        print(f"入库前表内 {cur.fetchone()[0]} 行")
        kept = title_d = few_d = short_d = 0
        for f in sorted(glob.glob(os.path.expanduser("~/workspace/dcard-full/batch33/*.jsonl"))):
            posts = {}
            for line in open(f, encoding="utf-8"):
                r = json.loads(line)
                posts.setdefault(r["post_id"], []).append(r)
            rows = []
            for pid, rs in posts.items():
                res, reason = build_row(rs)
                if reason == "title":
                    title_d += 1
                elif reason == "few":
                    few_d += 1
                elif reason == "no_post":
                    continue
                else:
                    row, short = res
                    short_d += short
                    rows.append(row)
            if rows:
                cur.executemany('''INSERT INTO forum."dcard"
                    (board, post_id, floor, posted_at_utc, post_title, body)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''', rows)
                conn.commit()
            kept += len(rows)
            print(f"{os.path.basename(f)}: 入 {len(rows)} 帖")
        cur.execute('SELECT COUNT(*) FROM forum."dcard"')
        print(f"batch33 合计入 {kept} 帖，弃标题 {title_d}，弃少回复 {few_d}，删短回复 {short_d} 条，入库后表内 {cur.fetchone()[0]} 行")
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
