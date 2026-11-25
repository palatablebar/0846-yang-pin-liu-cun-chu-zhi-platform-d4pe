# 字段定义

| 字段 | 类型 | 说明 |
|---|---|---|
| `sample_id` | text | 主键 |
| `study_id` | text | 业务字段 |
| `collected_at` | date | 业务字段 |
| `retention_months` | int | 业务字段 |
| `consent_until` | date_optional | 业务字段 |
| `legal_hold` | text | 业务字段 |
| `disposed_at` | date_optional | 业务字段 |
| `storage` | text | 业务字段 |

空字符串、`-`、`NA`、`null` 和 `未提供` 按空值处理。金额字段在整理层转为整数分或整数最小单位；日期按 ISO 日期解析；带时间的字段按本地时间解析。标识字段保持为文本，前导零不会被去除。

## 盘点对账提交（`POST /api/stocktake/submissions`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `stocktake_id` | text | 盘点单号，幂等键 |
| `warehouse` | text | 库房名称（可选） |
| `cutoff` | date | 盘点截点；只采信严格早于该日登记的凭据 |
| `book_records` | list | 账面记录，元素含 `location`、`sample_id` |
| `count_records` | list | 实盘记录，元素含 `location`、`sample_id` |
| `transfer_vouchers` | list | 发出凭据，含 `voucher_id`、`sample_id`、`from_location`、`to_location`、`due_date`、`registered_at` |
| `receipt_vouchers` | list | 签收凭据，含 `voucher_id`、`sample_id`、`registered_at` |

差异单返回分组：`in_transit`（在途）、`shortages`（短缺，含 `reason`）、`duplicates`（重号，含 `locations`）、`surplus`（多出）、`ignored_vouchers`（未采信凭据）、`summary`（计数汇总）。短缺原因码：`TRANSIT_OVERDUE`（在途逾期）、`NOT_COUNTED`（未盘到）、`LOCATION_MISMATCH`（库位不符）。
