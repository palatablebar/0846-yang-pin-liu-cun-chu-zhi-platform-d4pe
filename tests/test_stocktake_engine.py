"""盘点对账引擎规则测试，对应用户给出的全部业务规则。"""
from app.stocktake.engine import canonical_key, reconcile

CUTOFF = "2026-11-25"


def base_submission(**overrides):
    data = {
        "stocktake_id": "ST-T1",
        "cutoff": CUTOFF,
        "book_records": [],
        "count_records": [],
        "transfer_vouchers": [],
        "receipt_vouchers": [],
    }
    data.update(overrides)
    return data


def ids(rows, key="sample_id"):
    return [row[key] for row in rows]


def test_present_sample_has_no_discrepancy():
    """正常在库：无差异。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-1"}],
        count_records=[{"location": "A-01", "sample_id": "SP-1"}],
    ))
    assert result["summary"] == {"in_transit": 0, "shortage": 0, "duplicate": 0, "surplus": 0}
    assert result["has_discrepancy"] is False


def test_transferred_unsigned_within_due_is_in_transit_not_shortage():
    """已调出未签收、约定签收日未过：记在途，不算短缺（避免两边重复找货）。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-2"}],
        count_records=[],
        transfer_vouchers=[{"voucher_id": "TV-1", "sample_id": "SP-2",
                            "from_location": "A-01", "to_location": "B-01",
                            "due_date": "2026-11-30", "registered_at": "2026-11-20"}],
    ))
    assert ids(result["in_transit"]) == ["SP-2"]
    assert result["shortages"] == []
    assert result["has_discrepancy"] is False


def test_transferred_unsigned_overdue_is_from_location_shortage():
    """过了约定签收日仍未签收：记发出库位短缺。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-3"}],
        count_records=[],
        transfer_vouchers=[{"voucher_id": "TV-2", "sample_id": "SP-3",
                            "from_location": "A-01", "to_location": "B-01",
                            "due_date": "2026-11-20", "registered_at": "2026-11-18"}],
    ))
    assert result["in_transit"] == []
    assert len(result["shortages"]) == 1
    shortage = result["shortages"][0]
    assert shortage["sample_id"] == "SP-3"
    assert shortage["location"] == "A-01"
    assert shortage["reason"] == "TRANSIT_OVERDUE"


def test_signed_transfer_is_checked_at_destination():
    """截点前已签收：责任库位转到目的库位，在目的库位盘到即无差异。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-4"}],
        count_records=[{"location": "B-01", "sample_id": "SP-4"}],
        transfer_vouchers=[{"voucher_id": "TV-3", "sample_id": "SP-4",
                            "from_location": "A-01", "to_location": "B-01",
                            "due_date": "2026-11-24", "registered_at": "2026-11-19"}],
        receipt_vouchers=[{"voucher_id": "RV-1", "sample_id": "SP-4",
                           "registered_at": "2026-11-22"}],
    ))
    assert result["shortages"] == []
    assert result["in_transit"] == []


def test_same_sample_in_two_locations_is_duplicate():
    """两边都盘到同一件样品：报重。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-5"}],
        count_records=[{"location": "A-01", "sample_id": "SP-5"},
                       {"location": "B-09", "sample_id": "SP-5"}],
    ))
    assert len(result["duplicates"]) == 1
    assert result["duplicates"][0]["locations"] == ["A-01", "B-09"]


def test_duplicate_does_not_offset_shortage():
    """重号与短缺分别独立列示，差异不能相抵。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-5"},
                      {"location": "A-02", "sample_id": "SP-6"}],
        count_records=[{"location": "A-01", "sample_id": "SP-5"},
                       {"location": "B-09", "sample_id": "SP-5"}],
    ))
    assert ids(result["duplicates"]) == ["SP-5"]
    assert ids(result["shortages"]) == ["SP-6"]
    # 没有用 SP-5 的重号去抵消 SP-6 的短缺
    assert result["summary"]["duplicate"] == 1
    assert result["summary"]["shortage"] == 1


def test_same_location_double_count_is_duplicate():
    """同一库位同一样品盘到两次同样报重。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-7"}],
        count_records=[{"location": "A-01", "sample_id": "SP-7"},
                       {"location": "A-01", "sample_id": "SP-7"}],
    ))
    assert ids(result["duplicates"]) == ["SP-7"]


def test_receipt_registered_at_cutoff_is_not_accepted():
    """签收与盘点同时提交（登记日=截点日）：凭据不采信，仍按未签收记在途。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-8"}],
        count_records=[],
        transfer_vouchers=[{"voucher_id": "TV-4", "sample_id": "SP-8",
                            "from_location": "A-01", "to_location": "B-01",
                            "due_date": "2026-11-30", "registered_at": "2026-11-20"}],
        receipt_vouchers=[{"voucher_id": "RV-2", "sample_id": "SP-8",
                           "registered_at": CUTOFF}],
    ))
    assert ids(result["in_transit"]) == ["SP-8"]
    assert any(item["sample_id"] == "SP-8" for item in result["ignored_vouchers"])


def test_receipt_registered_after_cutoff_is_not_accepted():
    """截点之后登记的签收凭据不采信；逾期未签收记发出库位短缺。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-9"}],
        count_records=[],
        transfer_vouchers=[{"voucher_id": "TV-5", "sample_id": "SP-9",
                            "from_location": "A-01", "to_location": "B-01",
                            "due_date": "2026-11-20", "registered_at": "2026-11-18"}],
        receipt_vouchers=[{"voucher_id": "RV-3", "sample_id": "SP-9",
                           "registered_at": "2026-11-26"}],
    ))
    assert result["in_transit"] == []
    assert result["shortages"][0]["reason"] == "TRANSIT_OVERDUE"
    assert any(item["sample_id"] == "SP-9" for item in result["ignored_vouchers"])


def test_transfer_voucher_registered_at_cutoff_is_ignored():
    """发出凭据本身在截点当日才登记：不采信，按普通短缺处理。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-10"}],
        count_records=[],
        transfer_vouchers=[{"voucher_id": "TV-6", "sample_id": "SP-10",
                            "from_location": "A-01", "to_location": "B-01",
                            "due_date": "2026-11-30", "registered_at": CUTOFF}],
    ))
    assert result["in_transit"] == []
    assert result["shortages"][0]["reason"] == "NOT_COUNTED"


def test_missing_book_sample_is_shortage():
    """无在途凭据且未盘到：普通短缺。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-11"}],
        count_records=[],
    ))
    assert result["shortages"][0] == {
        "sample_id": "SP-11", "type": "SHORTAGE", "location": "A-01",
        "reason": "NOT_COUNTED", "detail": "责任库位在册但盘点截点前未盘到",
    }


def test_unbooked_sample_is_surplus():
    """账面没有却盘到：多出，独立列示。"""
    result = reconcile(base_submission(
        count_records=[{"location": "A-01", "sample_id": "SP-12"}],
    ))
    assert ids(result["surplus"]) == ["SP-12"]
    assert result["shortages"] == []


def test_location_mismatch_emits_shortage_and_surplus_without_offset():
    """实物在非责任库位：短缺与多出分别列示、不相抵。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-13"}],
        count_records=[{"location": "Z-01", "sample_id": "SP-13"}],
    ))
    assert result["shortages"][0]["location"] == "A-01"
    assert result["shortages"][0]["reason"] == "LOCATION_MISMATCH"
    assert result["surplus"][0]["location"] == "Z-01"
    assert result["summary"]["shortage"] == 1
    assert result["summary"]["surplus"] == 1


def test_in_transit_sample_counted_twice_still_reports_duplicate():
    """在途样品若被多库位盘到，重号仍独立报出，不被在途状态吞掉。"""
    result = reconcile(base_submission(
        book_records=[{"location": "A-01", "sample_id": "SP-15"}],
        count_records=[{"location": "B-01", "sample_id": "SP-15"},
                       {"location": "B-02", "sample_id": "SP-15"}],
        transfer_vouchers=[{"voucher_id": "TV-7", "sample_id": "SP-15",
                            "from_location": "A-01", "to_location": "B-01",
                            "due_date": "2026-11-30", "registered_at": "2026-11-20"}],
    ))
    assert ids(result["in_transit"]) == ["SP-15"]
    assert ids(result["duplicates"]) == ["SP-15"]
    assert result["shortages"] == []


def test_deterministic_canonical_key():
    """相同输入产生相同内容指纹（幂等重试的基础）。"""
    payload = base_submission(book_records=[{"location": "A-01", "sample_id": "SP-14"}],
                              count_records=[])
    first = canonical_key(reconcile(payload))
    second = canonical_key(reconcile(payload))
    assert first == second


def test_clean_sample_covers_every_rule():
    """干净样例同时覆盖在途、逾期短缺、重号、库位不符、多出、截点凭据不采信。"""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "sample_data" / "stocktake" / "clean.json"
    submission = json.loads(path.read_text(encoding="utf-8"))
    result = reconcile(submission)

    assert ids(result["in_transit"]) == ["SP-004"]
    shortage_ids = ids(result["shortages"])
    assert "SP-005" in shortage_ids  # 逾期未签收 -> 发出库位短缺
    assert "SP-009" in shortage_ids  # 库位不符短缺
    assert ids(result["duplicates"]) == ["SP-007"]
    assert ids(result["surplus"]) == ["SP-009", "SP-099"]
    # SP-004 的签收凭据与盘点同时提交，不采信
    assert any(item["sample_id"] == "SP-004" for item in result["ignored_vouchers"])
    # SP-010 截点前已签收并在目的库位盘到，无差异
    all_flagged = shortage_ids + ids(result["duplicates"]) + ids(result["surplus"])
    assert "SP-010" not in all_flagged
    assert result["summary"] == {"in_transit": 1, "shortage": 2, "duplicate": 1, "surplus": 2}
