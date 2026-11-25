from flask import Blueprint, jsonify, request, send_file

from app.config import ROOT
from app.errors import DomainIssue
from app.stocktake.service import submit_stocktake
from app.stocktake.store import StocktakeStore

stocktake_api = Blueprint("stocktake_api", __name__, url_prefix="/api/stocktake")
STOCKTAKE_SAMPLES = ROOT / "sample_data" / "stocktake"


def store():
    from flask import current_app
    return current_app.extensions["stocktake"]


@stocktake_api.get("/examples/<profile>")
def example(profile):
    if profile not in {"clean", "dirty"}:
        raise DomainIssue("SAMPLE_UNKNOWN", 404)
    return send_file(STOCKTAKE_SAMPLES / f"{profile}.json", as_attachment=False)


@stocktake_api.post("/submissions")
def submit():
    """提交一份盘点，对账后签发差异单；同盘点单号重试不重复登记。"""
    submission = request.get_json(silent=True)
    if not submission:
        raise DomainIssue("BAD_REQUEST")
    return jsonify(submit_stocktake(store(), submission))


@stocktake_api.get("/issues")
def list_issues():
    """列出已签发差异单（工作台核对入口）。"""
    return jsonify(issues=store().list_issues())


@stocktake_api.get("/issues/<issue_id>")
def get_issue(issue_id):
    row = store().get(issue_id)
    payload = StocktakeStore.deserialize(row)
    if payload is None:
        raise DomainIssue("ISSUE_NOT_FOUND", 404)
    return jsonify(payload)


@stocktake_api.get("/stocktakes/<stocktake_id>")
def get_by_stocktake(stocktake_id):
    row = store().find_by_stocktake(stocktake_id)
    payload = StocktakeStore.deserialize(row)
    if payload is None:
        raise DomainIssue("ISSUE_NOT_FOUND", 404)
    return jsonify(payload)
