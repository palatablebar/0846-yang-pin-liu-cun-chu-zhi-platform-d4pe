"""库房按库位盘点对账引擎。

输入一份盘点提交（账面库位、实盘库位、发出凭据、签收凭据、盘点截点），
输出差异单。规则：

1. 有发出凭据且盘点截点前未签收的样品先记在途，不算短缺；
   超过凭据约定签收日仍未签收，记发出库位短缺。
2. 同一件样品被两个库位同时盘到，报重；重号与短缺分别独立列示，差异不相抵。
3. 差异单只认盘点截点之前已登记的凭据；与盘点同时提交（登记日等于截点日）
   或截点之后登记的凭据一律不采信。
4. 同一份盘点（同一盘点单号）重试提交不重复登记，由服务层保证幂等。
"""
from datetime import date


def _parse_date(value):
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    return date.fromisoformat(str(value))


def _registered_on_time(voucher, cutoff):
    """凭据登记时间严格早于盘点截点才采信。

    规则：签收与盘点同时提交时，差异单只认盘点截点前已登记的凭据，
    因此登记日等于截点日（同时提交）的凭据不采信。
    """
    registered = _parse_date(voucher.get("registered_at"))
    return registered is not None and registered < cutoff


def _group_counts(records):
    """按库位归集，同一库位内同一样品出现多次也保留数量。"""
    grouped = {}
    for record in records:
        location = str(record["location"])
        sample_id = str(record["sample_id"])
        grouped.setdefault(location, {})
        grouped[location][sample_id] = grouped[location].get(sample_id, 0) + 1
    return grouped


def _invert_counts(grouped):
    """样品 -> 盘到该样品的库位列表（含同库位重复计数）。"""
    seen = {}
    for location, samples in grouped.items():
        for sample_id, qty in samples.items():
            seen.setdefault(sample_id, [])
            for _ in range(qty):
                seen[sample_id].append(location)
    return seen


def reconcile(submission):
    """对一份盘点提交执行对账，返回差异单结构（纯函数，无副作用）。"""
    cutoff = _parse_date(submission["cutoff"])
    book = _group_counts(submission.get("book_records", []))
    counted = _group_counts(submission.get("count_records", []))
    counted_by_sample = _invert_counts(counted)

    transfers = {}
    ignored_transfers = []
    for voucher in submission.get("transfer_vouchers", []):
        sample_id = str(voucher["sample_id"])
        if not _registered_on_time(voucher, cutoff):
            ignored_transfers.append({"sample_id": sample_id,
                                      "voucher_id": str(voucher["voucher_id"]),
                                      "reason": "REGISTERED_AFTER_CUTOFF"})
            continue
        transfers[sample_id] = {
            "voucher_id": str(voucher["voucher_id"]),
            "from_location": str(voucher["from_location"]),
            "to_location": str(voucher["to_location"]),
            "due_date": _parse_date(voucher["due_date"]),
            "registered_at": _parse_date(voucher["registered_at"]),
        }

    receipts = set()
    ignored_receipts = []
    for voucher in submission.get("receipt_vouchers", []):
        sample_id = str(voucher["sample_id"])
        if _registered_on_time(voucher, cutoff):
            receipts.add(sample_id)
        else:
            ignored_receipts.append({"sample_id": sample_id,
                                     "voucher_id": str(voucher["voucher_id"]),
                                     "reason": "REGISTERED_AFTER_CUTOFF"})

    shortages = []
    in_transit = []
    duplicates = []
    surplus = []

    all_samples = set()
    for samples in book.values():
        all_samples.update(samples)
    all_samples.update(counted_by_sample)

    for sample_id in sorted(all_samples):
        transfer = transfers.get(sample_id)
        signed = sample_id in receipts
        counted_locations = counted_by_sample.get(sample_id, [])
        book_owner = next((loc for loc, samples in book.items() if sample_id in samples), None)

        # 规则 2：同一件样品被两个库位（或同一库位多条记录）盘到 -> 重号。
        # 重号独立列示，不与任何短缺相抵。
        if len(counted_locations) > 1:
            duplicates.append({
                "sample_id": sample_id,
                "type": "DUPLICATE",
                "locations": sorted(counted_locations),
                "detail": "同一样品在多个库位被盘到，差异不相抵",
            })

        if transfer and not signed:
            # 规则 1：已调出、截点前未签收，先记在途；约定签收日已过则发出库位短缺。
            entry = {
                "sample_id": sample_id,
                "voucher_id": transfer["voucher_id"],
                "from_location": transfer["from_location"],
                "to_location": transfer["to_location"],
                "due_date": transfer["due_date"].isoformat(),
            }
            if transfer["due_date"] >= cutoff:
                in_transit.append(dict(entry, type="IN_TRANSIT",
                                       detail="已调出未签收，约定签收日未过，记在途不计短缺"))
            else:
                shortages.append(dict(entry, type="SHORTAGE", location=transfer["from_location"],
                                      reason="TRANSIT_OVERDUE",
                                      detail="超过约定签收日仍未签收，记发出库位短缺"))
            continue

        # 已签收的转移：责任库位转移到目的库位，按目的库位核对。
        if transfer and signed:
            expected_location = transfer["to_location"]
        else:
            expected_location = book_owner

        if expected_location is None:
            # 账面与有效凭据中都不存在却盘到 -> 多出（独立列示，不参与相抵）。
            if counted_locations:
                surplus.append({
                    "sample_id": sample_id,
                    "type": "SURPLUS",
                    "location": sorted(counted_locations)[0],
                    "detail": "账面无记录但实盘存在",
                })
            continue

        if not counted_locations:
            shortages.append({
                "sample_id": sample_id,
                "type": "SHORTAGE",
                "location": expected_location,
                "reason": "NOT_COUNTED",
                "detail": "责任库位在册但盘点截点前未盘到",
            })
        elif expected_location not in counted_locations and len(counted_locations) == 1:
            # 只在别的库位盘到、且不是多库位重号：库位不符，短缺与多出分别列示、不相抵。
            shortages.append({
                "sample_id": sample_id,
                "type": "SHORTAGE",
                "location": expected_location,
                "reason": "LOCATION_MISMATCH",
                "detail": f"责任库位 {expected_location} 未盘到，实物出现于 {counted_locations[0]}",
            })
            surplus.append({
                "sample_id": sample_id,
                "type": "SURPLUS",
                "location": counted_locations[0],
                "detail": f"实物在非责任库位 {counted_locations[0]} 盘到",
            })

    discrepancy = {
        "schema": "stocktake-discrepancy/v1",
        "stocktake_id": str(submission["stocktake_id"]),
        "cutoff": cutoff.isoformat(),
        "warehouse": submission.get("warehouse", ""),
        "ignored_vouchers": ignored_transfers + ignored_receipts,
        "in_transit": in_transit,
        "shortages": shortages,
        "duplicates": duplicates,
        "surplus": surplus,
        "summary": {
            "in_transit": len(in_transit),
            "shortage": len(shortages),
            "duplicate": len(duplicates),
            "surplus": len(surplus),
        },
    }
    discrepancy["has_discrepancy"] = bool(shortages or duplicates or surplus)
    return discrepancy


def canonical_key(discrepancy):
    """差异单内容指纹：同盘点单 + 同截点 + 同输入应得到同一指纹，用于幂等校验。"""
    import hashlib
    import json

    body = json.dumps(
        {k: v for k, v in discrepancy.items() if k not in {"issue_id", "issued_at", "schema"}},
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
