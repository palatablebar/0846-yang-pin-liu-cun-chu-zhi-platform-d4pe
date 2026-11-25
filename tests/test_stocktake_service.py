"""差异单签发：幂等重试、冲突保护与校验。"""
import json
from pathlib import Path

import pytest

from app.errors import DomainIssue
from app.stocktake.service import submit_stocktake
from app.stocktake.store import StocktakeStore

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "stocktake"


def load(name):
    return json.loads((SAMPLE / name).read_text(encoding="utf-8"))


@pytest.fixture
def store(tmp_path):
    return StocktakeStore(str(tmp_path / "stocktake.sqlite3"))


def test_first_submission_creates_issue(store):
    result = submit_stocktake(store, load("clean.json"))
    assert result["outcome"] == "CREATED"
    assert result["issue_id"].startswith("DIFF-")
    assert result["stocktake_id"] == "ST-2026-1125-A"
    assert result["summary"]["shortage"] == 2


def test_retry_does_not_duplicate_registration(store):
    """同一份盘点重试：不重复登记差异，返回原单。"""
    first = submit_stocktake(store, load("clean.json"))
    second = submit_stocktake(store, load("clean.json"))
    assert second["outcome"] == "EXISTING"
    assert second["issue_id"] == first["issue_id"]
    assert len(store.list_issues()) == 1


def test_same_id_different_content_is_conflict(store):
    """同盘点单号但内容不同：拒绝覆盖。"""
    payload = load("clean.json")
    submit_stocktake(store, payload)
    changed = json.loads(json.dumps(payload))
    changed["count_records"].append({"location": "X-01", "sample_id": "SP-NEW"})
    with pytest.raises(DomainIssue) as exc:
        submit_stocktake(store, changed)
    assert exc.value.code == "STOCKTAKE_CONFLICT"
    assert exc.value.status == 409


def test_missing_required_field_is_rejected(store):
    payload = load("dirty.json")
    with pytest.raises(DomainIssue) as exc:
        submit_stocktake(store, payload)
    assert exc.value.code == "BAD_REQUEST"


def test_missing_stocktake_id_is_rejected(store):
    payload = load("clean.json")
    del payload["stocktake_id"]
    with pytest.raises(DomainIssue):
        submit_stocktake(store, payload)


def test_find_by_stocktake_returns_issued_report(store):
    issued = submit_stocktake(store, load("clean.json"))
    fetched = StocktakeStore.deserialize(store.find_by_stocktake("ST-2026-1125-A"))
    assert fetched["issue_id"] == issued["issue_id"]
    assert fetched["shortages"] == issued["shortages"]


def test_invalid_date_is_rejected(store):
    payload = load("clean.json")
    payload["cutoff"] = "2026-13-99"
    with pytest.raises(DomainIssue) as exc:
        submit_stocktake(store, payload)
    assert exc.value.code == "BAD_REQUEST"


def test_non_dict_payload_is_rejected(store):
    with pytest.raises(DomainIssue):
        submit_stocktake(store, ["not", "a", "dict"])
