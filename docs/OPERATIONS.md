# 运行说明

## 启动

```bash
docker compose up --build
```

## 测试

```bash
docker compose exec -T app pytest -q
```

## 样例

- `dirty`：包含编码、列数、空值或冲突重复，适合检查隔离区。
- `clean`：可通过当前规则并完成签发。

## 重置

```bash
docker compose down -v
docker compose up --build
```

历史批次保存在 SQLite 卷中。重置会清除本地批次与签发记录。

## 库房盘点对账

- 工作台页面：`/stocktake`。
- 样例：`sample_data/stocktake/clean.json` 覆盖在途、逾期短缺、重号、库位不符、多出与截点凭据不采信；`dirty.json` 触发必填校验拒绝。
- 已签发差异单持久化在卷内 `stocktake.sqlite3`，同一盘点单号重试不重复登记。
- 规则见 `docs/STOCKTAKE-RULES.md`，测试见 `tests/test_stocktake_*.py`。
