#!/usr/bin/env python3
"""Dcard 样本过滤（用户 2026-11-04 23:38 规则）：
- 标题去空白后少于 10 字，整帖不要
- 回复总数（留言+子留言）为 0 或少于 5，整帖不要
- 回复正文去空白后少于 10 字，只删该条回复，主帖保留
- 顺序：先删短回复，再按剩下的回复数判断帖子
- 口令只从环境变量 DBPASS 读，不写进文件
"""
import os, sys

POST_ID = 262397922
BOARD = "relationship"

def main():
    pw = os.environ.get("DBPASS")
    if not pw:
        print("DBPASS 未设置，拒绝连接", file=sys.stderr)
        return 2
    import psycopg
    conn = psycopg.connect(host="127.0.0.1", port=15432, dbname="postgres",
                           user="postgres", password=pw, connect_timeout=30)
    try:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM forum."dcard" WHERE board=%s AND post_id=%s', (BOARD, POST_ID))
        before = cur.fetchone()[0]
        cur.execute('SELECT post_title FROM forum."dcard" WHERE board=%s AND post_id=%s AND floor=%s', (BOARD, POST_ID, "0"))
        title = cur.fetchone()[0]
        import re
        title_len = len(re.sub(r"\s+", "", title or ""))
        cur.execute('SELECT COUNT(*) FROM forum."dcard" WHERE board=%s AND post_id=%s AND floor<>%s', (BOARD, POST_ID, "0"))
        replies_before = cur.fetchone()[0]
        cur.execute('''SELECT floor, body FROM forum."dcard"
                       WHERE board=%s AND post_id=%s AND floor<>%s
                       AND LENGTH(REGEXP_REPLACE(body, '\\s+', '', 'g')) < 10
                       ORDER BY floor''', (BOARD, POST_ID, "0"))
        short = cur.fetchall()
        print(f"标题去空白 {title_len} 字，过滤前 {before} 行（主帖 1、回复 {replies_before} 条），短回复 {len(short)} 条")
        for floor, body in short:
            print(f"  删 {floor} | {(body or '')[:40]}")
        if short:
            cur.execute('''DELETE FROM forum."dcard"
                           WHERE board=%s AND post_id=%s AND floor<>%s
                           AND LENGTH(REGEXP_REPLACE(body, '\\s+', '', 'g')) < 10''', (BOARD, POST_ID, "0"))
            print(f"  已删 {cur.rowcount} 行")
        cur.execute('SELECT COUNT(*) FROM forum."dcard" WHERE board=%s AND post_id=%s AND floor<>%s', (BOARD, POST_ID, "0"))
        replies_after = cur.fetchone()[0]
        print(f"删短回复后回复剩 {replies_after} 条")
        if title_len < 10 or replies_after < 5:
            cur.execute('DELETE FROM forum."dcard" WHERE board=%s AND post_id=%s', (BOARD, POST_ID))
            print(f"整帖不达标（标题 {title_len} 字、回复 {replies_after} 条），已删整帖 {cur.rowcount} 行")
        else:
            print("整帖达标，保留")
        conn.commit()
        cur.execute('SELECT COUNT(*) FROM forum."dcard" WHERE board=%s AND post_id=%s', (BOARD, POST_ID))
        after = cur.fetchone()[0]
        cur.execute('SELECT floor FROM forum."dcard" WHERE board=%s AND post_id=%s ORDER BY floor', (BOARD, POST_ID))
        floors = [r[0] for r in cur.fetchall()]
        print(f"过滤后查回 {after} 行，楼层：{', '.join(floors)}")
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
