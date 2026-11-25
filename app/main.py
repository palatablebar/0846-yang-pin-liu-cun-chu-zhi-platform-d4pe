import os
from pathlib import Path

from flask import Flask, jsonify, render_template
from werkzeug.exceptions import RequestEntityTooLarge

from app.catalog import SPEC
from app.config import MAX_FILE, ROOT
from app.errors import DomainIssue, error_response
from app.review.store import Store
from app.routes import api
from app.stocktake.routes import stocktake_api
from app.stocktake.store import StocktakeStore


def create_app(database=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE + 64 * 1024
    app.extensions["runs"] = Store(database or os.getenv("WORKBENCH_DB", str(ROOT / "instance" / "workbench.sqlite3")))
    stocktake_db = os.getenv("STOCKTAKE_DB", str(ROOT / "instance" / "stocktake.sqlite3"))
    app.extensions["stocktake"] = StocktakeStore(
        stocktake_db if database is None else str(Path(database).parent / "stocktake.sqlite3")
    )
    app.register_error_handler(DomainIssue, error_response)
    app.register_error_handler(RequestEntityTooLarge, lambda _: error_response(DomainIssue("FILE_TOO_LARGE", 413)))
    app.register_blueprint(api)
    app.register_blueprint(stocktake_api)

    @app.get("/")
    def home():
        return render_template("index.html", p=SPEC)

    @app.get("/stocktake")
    def stocktake_home():
        return render_template("stocktake.html")

    @app.get("/healthz")
    def health():
        return jsonify(status="ok")

    return app


app = create_app()
