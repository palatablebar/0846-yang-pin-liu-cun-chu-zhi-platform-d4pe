"""盘点对账 HTTP 接口测试。"""
import json
from pathlib import Path

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "stocktake"


def load(profile="clean"):
    return json.loads((SAMPLE / f"{profile}.json").read_text(encoding="utf-8"))


def test_submit_returns_issued_discrepancy(client):
    response = client.post("/api/stocktake/submissions", json=load("clean"))
    assert response.status_code == 200
    body = response.get_json()
    assert body["schema"] == "stocktake-discrepancy/v1"
    assert body["issue_id"].startswith("DIFF-")
    assert body["outcome"] == "CREATED"


def test_retry_submission_is_idempotent_over_http(client):
    payload = load("clean")
    first = client.post("/api/stocktake/submissions", json=payload).get_json()
    second = client.post("/api/stocktake/submissions", json=payload).get_json()
    assert second["outcome"] == "EXISTING"
    assert second["issue_id"] == first["issue_id"]
    listing = client.get("/api/stocktake/issues").get_json()["issues"]
    assert len(listing) == 1


def test_get_issue_and_get_by_stocktake(client):
    issued = client.post("/api/stocktake/submissions", json=load("clean")).get_json()
    by_id = client.get(f"/api/stocktake/issues/{issued['issue_id']}")
    assert by_id.status_code == 200
    assert by_id.get_json()["stocktake_id"] == issued["stocktake_id"]

    by_stocktake = client.get(f"/api/stocktake/stocktakes/{issued['stocktake_id']}")
    assert by_stocktake.status_code == 200
    assert by_stocktake.get_json()["issue_id"] == issued["issue_id"]


def test_unknown_issue_returns_404(client):
    response = client.get("/api/stocktake/issues/DIFF-NOPE")
    assert response.status_code == 404
    assert response.get_json()["code"] == "ISSUE_NOT_FOUND"


def test_conflicting_submission_returns_409(client):
    payload = load("clean")
    client.post("/api/stocktake/submissions", json=payload)
    payload["count_records"].append({"location": "X-01", "sample_id": "SP-NEW"})
    response = client.post("/api/stocktake/submissions", json=payload)
    assert response.status_code == 409
    assert response.get_json()["code"] == "STOCKTAKE_CONFLICT"


def test_bad_payload_returns_400(client):
    response = client.post("/api/stocktake/submissions", json=load("dirty"))
    assert response.status_code == 400
    assert response.get_json()["code"] == "BAD_REQUEST"


def test_empty_body_returns_400(client):
    response = client.post("/api/stocktake/submissions", data="", content_type="application/json")
    assert response.status_code == 400


def test_stocktake_page_renders(client):
    response = client.get("/stocktake")
    assert response.status_code == 200
    assert "库房盘点对账台".encode() in response.data


def test_example_endpoint_serves_samples(client):
    response = client.get("/api/stocktake/examples/clean")
    assert response.status_code == 200
    assert response.get_json()["stocktake_id"] == "ST-2026-1125-A"
    assert client.get("/api/stocktake/examples/unknown").status_code == 404
