#!/usr/bin/env python3
"""Dcard 样本入库（Windows Postgres，极简 6 栏，与 5ch / hkgolden 表同形）：
- 表：forum."dcard"（board, post_id, floor, posted_at_utc, post_title, body），主键 (board, post_id, floor)
- floor：主帖 0，顶层留言用 Dcard 楼层，子留言用「父楼层.子楼层」（如 1.1），TEXT 栏位
- 时间：Dcard created_at 本身就是 UTC（Z），去掉时区存为不带时区的 timestamp
- 不写作者、昵称、头像、学校等字段，不写网址栏位、不写数组；正文原样
- 样本：relationship 板 262397922，共 19 行，已存在则不重复写
- 口令绝不写进文件：只从环境变量 DBPASS 读，进程结束即丢
- 连库走已有的本地 socat 转发（127.0.0.1:15432 -> Windows:5432），本脚本只连 127.0.0.1
"""
import json, os, sys
from datetime import datetime, timezone

POST_ID = 262397922
SRC = os.path.expanduser("~/workspace/dcard-full/batch1/relationship.jsonl")

def parse_utc(s):
    if not s:
        return None
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

def main():
    pw = os.environ.get("DBPASS")
    if not pw:
        print("DBPASS 未设置，拒绝连接", file=sys.stderr)
        return 2
    import psycopg
    rows_raw = []
    for line in open(SRC, encoding="utf-8"):
        r = json.loads(line)
        if r["post_id"] == POST_ID:
            rows_raw.append(r)
    post = next(r for r in rows_raw if r["type"] == "post")
    parent_floor = {}
    for r in rows_raw:
        if r["type"] == "comment":
            parent_floor[r["comment_id"]] = r["floor"]
    rows = []
    for r in rows_raw:
        if r["type"] == "post":
            floor = "0"
        elif r["type"] == "comment":
            floor = str(r["floor"])
        else:
            pf = parent_floor.get(r["parent_comment_id"])
            floor = f"{pf}.{r['floor']}" if pf is not None else str(r["floor"])
        rows.append((post["forum_alias"], POST_ID, floor, parse_utc(r["created_at"]),
                     post["title"] or "", r.get("content") or ""))
    # 按 floor 排序：0, 1, 1.1, 1.2, ..., 2, 2.1, ...
    def floor_key(x):
        return tuple(int(p) for p in x[2].split("."))
    rows.sort(key=floor_key)
    conn = psycopg.connect(host="127.0.0.1", port=15432, dbname="postgres",
                           user="postgres", password=pw, connect_timeout=30)
    try:
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS forum")
        cur.execute('''CREATE TABLE IF NOT EXISTS forum."dcard" (
            board TEXT, post_id BIGINT, floor TEXT,
            posted_at_utc TIMESTAMP WITHOUT TIME ZONE,
            post_title TEXT, body TEXT,
            PRIMARY KEY (board, post_id, floor))''')
        cur.execute('SELECT COUNT(*) FROM forum."dcard" WHERE board=%s AND post_id=%s',
                    (rows[0][0], POST_ID))
        before = cur.fetchone()[0]
        cur.executemany('''INSERT INTO forum."dcard"
            (board, post_id, floor, posted_at_utc, post_title, body)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''', rows)
        conn.commit()
        cur.execute('SELECT floor, posted_at_utc, LEFT(body, 40) FROM forum."dcard" '
                    'WHERE board=%s AND post_id=%s ORDER BY floor',
                    (rows[0][0], POST_ID))
        back = cur.fetchall()
        print(f"样本帖 {POST_ID}：文件 {len(rows)} 行，入库前已有 {before} 行，查回 {len(back)} 行")
        for floor, ts, snippet in back:
            print(f"  {floor} | {ts} | {snippet}")
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
