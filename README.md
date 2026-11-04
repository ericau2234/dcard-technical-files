# Dcard 入库技术文件

只含入库脚本，不含帖子正文数据，不含数据库口令。

## 表

`forum."dcard"`，6 栏：`board, post_id, floor, posted_at_utc, post_title, body`，
主键 `(board, post_id, floor)`，一帖一行，`floor` 固定为 `0`。

## 格式

主帖正文在前，剩余评论按楼层顺序拼在同一行 `body` 里，
每条评论前加 `[楼层 X]`（顶层为楼层，子留言为父楼层.子楼层）。

## 过滤（打包前按条做）

- 标题去空白后少于 10 字，整帖不要
- 回复正文去空白后少于 10 字，只删该条回复
- 删后回复少于 5 条，整帖不要

## 脚本

- `import_sample_dcard.py`：样本帖入库（原一评论一行格式）
- `filter_sample_dcard.py`：样本过滤
- `merge_sample_one_row.py`：样本改成一帖一行
- `import_full_one_row.py`：batch1-17 全量入库，一帖一行
- `import_batch_one_row.py`：单批补入，用法 `DBPASS=... python3 import_batch_one_row.py <批号>`

## 连接

口令只从环境变量 `DBPASS` 读，不写进脚本。
连库走本地转发 `127.0.0.1:15432`，脚本本身只连这个地址。
