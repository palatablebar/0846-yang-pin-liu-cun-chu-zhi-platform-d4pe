# 样品留存处置台

生物样本库管理员处理留存期限与保全优先级的本地工作台。样例、规则和复核记录都在项目内，不依赖外部服务。

## 启动

```bash
docker compose up --build
```

打开 `http://127.0.0.1:${PORT:-18520}`。默认端口见 `docker-compose.yml`。

## 验证

```bash
docker compose exec -T app pytest -q
docker compose config --quiet
```

## 操作

1. 在左侧选阶段，查看采信、整理、计算、判定和对账结果。
2. 选择 `dirty` 样例观察坏行和隔离原因。
3. 换 `clean` 样例执行批次，填写复核意见后签发。
4. 下载证据 JSON，核对来源摘要、指标和签发版本。

业务规则见 `docs/BUSINESS-RULES.md`，字段定义见 `docs/DATA-DICTIONARY.md`。

## 库房盘点对账

按库位盘点对账并签发差异单，工作台入口 `/stocktake`：

- 已调出未签收先记在途；过约定签收日未签收记发出库位短缺。
- 同一样品多处盘到报重，重号与短缺/多出独立列示、不相抵。
- 只采信盘点截点前已登记的凭据；同盘点单重试不重复登记。

规则见 `docs/STOCKTAKE-RULES.md`，接口见 `docs/HTTP.md`。
