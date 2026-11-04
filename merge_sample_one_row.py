#!/usr/bin/env python3
"""Dcard 样本改成一帖一行：主帖 + 全部剩余评论塞进同一行的 body，
按楼层顺序、每条前加 [楼层 X] 标记，仍是同一张表、同一 6 栏。
口令只从环境变量 DBPASS 读，不写进文件。"""
import os, sys

BOARD = "relationship"
POST_ID = 262397922

def floor_key(f):
    return tuple(int(x) for x in str(f).split("."))

def main():
    pw = os.environ.get("DBPASS")
    if not pw:
        print("DBPASS 未设置", file=sys.stderr)
        return 2
    import psycopg
    conn = psycopg.connect(host="127.0.0.1", port=15432, dbname="postgres",
                           user="postgres", password=pw, connect_timeout=30)
    try:
        cur = conn.cursor()
        cur.execute('SELECT floor, posted_at_utc, post_title, body FROM forum."dcard" '
                    'WHERE board=%s AND post_id=%s', (BOARD, POST_ID))
        rows = cur.fetchall()
        print(f"合并前 {len(rows)} 行")
        rows.sort(key=lambda r: floor_key(r[0]))
        main = [r for r in rows if r[0] == "0"]
        if not main:
            print("找不到主帖行", file=sys.stderr)
            return 3
        main = main[0]
        parts = [main[3] or ""]
        for floor, _ts, _title, body in rows:
            if floor == "0":
                continue
            parts.append(f"\n\n[楼层 {floor}]\n{body or ''}")
        merged = "".join(parts)
        print(f"合并后正文 {len(merged)} 字，含楼层标记 {merged.count('[楼层 ')} 条")
        print(f"含 2.8 标记：{'[楼层 2.8]' in merged}")
        cur.execute('DELETE FROM forum."dcard" WHERE board=%s AND post_id=%s', (BOARD, POST_ID))
        cur.execute('INSERT INTO forum."dcard" (board, post_id, floor, posted_at_utc, post_title, body) '
                    'VALUES (%s, %s, %s, %s, %s, %s)',
                    (BOARD, POST_ID, "0", main[1], main[2], merged))
        conn.commit()
        cur.execute('SELECT COUNT(*) FROM forum."dcard" WHERE board=%s AND post_id=%s', (BOARD, POST_ID))
        print(f"合并后查回 {cur.fetchone()[0]} 行")
        cur.execute('SELECT floor, post_title, LENGTH(body) FROM forum."dcard" WHERE board=%s AND post_id=%s', (BOARD, POST_ID))
        print(cur.fetchone())
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
