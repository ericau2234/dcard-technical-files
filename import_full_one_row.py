#!/usr/bin/env python3
"""Dcard 全量入库，一帖一行（用户 2026-11-04 23:44 定、23:47 说 copy 入）：
- 范围：batch1-17 已完成批次，batch18 仍在爬、不入
- 过滤（23:38 规则，打包前按条做）：标题去空白 <10 字整帖不要；
  回复正文去空白 <10 字只删该条；删后回复 <5 条整帖不要
- 一行：主帖正文在前，剩余评论按楼层顺序拼后，每条前加 [楼层 X]
  （顶层为楼层，子留言为 父楼层.子楼层），同一张表、同一 6 栏，floor 固定 0
- 口令只从环境变量 DBPASS 读，不写进文件；每板文件提交一次，已存在则不重复写
"""
import json, os, re, sys, glob
from datetime import datetime, timezone

def clean(s):
    return re.sub(r"\s+", "", s or "")

def parse_utc(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)

def build_row(rs):
    post = next((r for r in rs if r["type"] == "post"), None)
    if not post:
        return None, "no_post"
    if len(clean(post.get("title") or "")) < 10:
        return None, "title"
    tops = sorted([r for r in rs if r["type"] == "comment"], key=lambda r: r.get("floor") or 0)
    subs_by_parent = {}
    for r in rs:
        if r["type"] == "subcomment":
            subs_by_parent.setdefault(r.get("parent_comment_id"), []).append(r)
    for v in subs_by_parent.values():
        v.sort(key=lambda r: r.get("floor") or 0)
    ordered = []  # (label, content)
    short = 0
    for t in tops:
        if len(clean(t.get("content") or "")) < 10:
            short += 1
            # 该顶层留言被删，其子留言按原楼层仍保留？按此前样本做法：只删该条本身，
            # 子留言仍按父楼层归属保留，避免整串丢失；若用户要整串删，再改。
            # 实际上此前样本无此情况；此处为保险，子留言仍保留。
            pass
        else:
            ordered.append((str(t["floor"]), t.get("content") or ""))
        for s in subs_by_parent.get(t.get("comment_id"), []):
            if len(clean(s.get("content") or "")) < 10:
                short += 1
                continue
            ordered.append((f"{t['floor']}.{s['floor']}", s.get("content") or ""))
    # 顶层被删时其子留言已在上面保留（label 仍用原父楼层），不影响计数
    if len(ordered) < 5:
        return None, "few"
    parts = [post.get("content") or ""]
    for label, content in ordered:
        parts.append(f"\n\n[楼层 {label}]\n{content}")
    row = (post.get("forum_alias"), post["post_id"], "0",
           parse_utc(post.get("created_at")), post.get("title") or "", "".join(parts))
    return (row, short), None

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
        cur.execute('SELECT COUNT(*) FROM forum."dcard"')
        before = cur.fetchone()[0]
        print(f"入库前表内 {before} 行")
        total_kept = total_title = total_few = total_short = 0
        for b in range(1, 18):
            kept = title_d = few_d = short_d = 0
            files = sorted(glob.glob(os.path.expanduser(f"~/workspace/dcard-full/batch{b}/*.jsonl")))
            for f in files:
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
            print(f"batch{b}: 入 {kept} 帖，弃标题 {title_d}，弃少回复 {few_d}，删短回复 {short_d} 条")
            total_kept += kept; total_title += title_d; total_few += few_d; total_short += short_d
        cur.execute('SELECT COUNT(*) FROM forum."dcard"')
        after = cur.fetchone()[0]
        print(f"合计入 {total_kept} 帖（已含样本帖，重复不计），弃标题 {total_title}，弃少回复 {total_few}，删短回复 {total_short} 条")
        print(f"入库后表内 {after} 行")
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
