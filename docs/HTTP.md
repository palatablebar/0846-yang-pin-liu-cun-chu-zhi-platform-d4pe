# 接口

- `GET /`：工作台。
- `GET /api/catalog`：阶段、字段和样例。
- `POST /api/stages/{stage}`：按阶段返回处理结果。
- `POST /api/runs`：执行完整批次并保存草稿。
- `GET /api/runs/{id}`：读取批次。
- `POST /api/runs/{id}/review`：签发或暂缓，提交 `decision`、`comment`、`expected_revision`。
- `GET /api/runs/{id}/evidence`：下载已签发证据。
- `GET /api/examples/{profile}`：下载样例。
- `GET /healthz`：健康检查。

## 库房盘点对账

- `GET /stocktake`：盘点对账工作台页面。
- `GET /api/stocktake/examples/{profile}`：盘点样例（`clean` / `dirty`）。
- `POST /api/stocktake/submissions`：提交盘点，对账并签发差异单；同盘点单号重试不重复登记。
- `GET /api/stocktake/issues`：列出已签发差异单（核对入口）。
- `GET /api/stocktake/issues/{issue_id}`：按差异单号读取明细。
- `GET /api/stocktake/stocktakes/{stocktake_id}`：按盘点单号读取已签发差异单。
