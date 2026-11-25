"""盘点对账服务层：校验提交、执行对账、幂等签发。"""
from datetime import date

from app.errors import DomainIssue
from app.stocktake.engine import canonical_key, reconcile
from app.stocktake.store import StocktakeStore

REQUIRED_FIELDS = ("stocktake_id", "cutoff")
RECORD_FIELDS = ("location", "sample_id")
VOUCHER_FIELDS = ("voucher_id", "sample_id", "from_location", "to_location",
                  "due_date", "registered_at")
RECEIPT_FIELDS = ("voucher_id", "sample_id", "registered_at")
DATE_FIELDS = ("cutoff", "due_date", "registered_at")


def _check_fields(record, fields, code="BAD_REQUEST"):
    missing = [name for name in fields if record.get(name) in (None, "")]
    if missing:
        raise DomainIssue(code, detail=f"缺少必填字段: {','.join(missing)}")


def _check_date(record, field):
    value = record.get(field)
    if value in (None, ""):
        return
    if isinstance(value, date):
        return
    try:
        date.fromisoformat(str(value))
    except ValueError:
        raise DomainIssue("BAD_REQUEST", detail=f"日期字段 {field} 不是合法 ISO 日期: {value}")


def validate(submission):
    if not isinstance(submission, dict):
        raise DomainIssue("BAD_REQUEST")
    _check_fields(submission, REQUIRED_FIELDS)
    _check_date(submission, "cutoff")
    for bucket in ("book_records", "count_records"):
        for record in submission.get(bucket, []):
            _check_fields(record, RECORD_FIELDS)
    for voucher in submission.get("transfer_vouchers", []):
        _check_fields(voucher, VOUCHER_FIELDS)
        _check_date(voucher, "due_date")
        _check_date(voucher, "registered_at")
    for voucher in submission.get("receipt_vouchers", []):
        _check_fields(voucher, RECEIPT_FIELDS)
        _check_date(voucher, "registered_at")


def submit_stocktake(store: StocktakeStore, submission):
    """对账并签发差异单；同一盘点单重试返回原单，不重复登记。"""
    validate(submission)
    discrepancy = reconcile(submission)
    content_hash = canonical_key(discrepancy)
    row, outcome = store.issue(submission["stocktake_id"], discrepancy, content_hash)
    if outcome == "CONFLICT":
        raise DomainIssue("STOCKTAKE_CONFLICT", 409,
                          "同一盘点单号存在内容不同的提交，拒绝覆盖")
    payload = StocktakeStore.deserialize(row)
    payload["outcome"] = outcome  # CREATED 或 EXISTING（重试）
    return payload
