"""差异单签发存储：同一份盘点重试提交不重复登记。"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


class StocktakeStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=8)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self):
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS discrepancy_issues(
              issue_id TEXT PRIMARY KEY,
              stocktake_id TEXT UNIQUE NOT NULL,
              content_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              payload TEXT NOT NULL
            );
            ''')

    def issue(self, stocktake_id, discrepancy, content_hash):
        """签发差异单。

        同一盘点单号已有签发记录时直接返回原单（重试不重复登记）；
        若同号但内容指纹变化，返回冲突，防止用同号覆盖不同盘点。
        """
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM discrepancy_issues WHERE stocktake_id=?", (stocktake_id,)
            ).fetchone()
            if existing:
                if existing["content_hash"] != content_hash:
                    return None, "CONFLICT"
                return dict(existing), "EXISTING"
            issue_id = "DIFF-" + uuid.uuid4().hex[:10].upper()
            created_at = datetime.now(timezone.utc).isoformat()
            record = dict(discrepancy)
            record["issue_id"] = issue_id
            record["issued_at"] = created_at
            db.execute(
                "INSERT INTO discrepancy_issues(issue_id,stocktake_id,content_hash,created_at,payload) "
                "VALUES(?,?,?,?,?)",
                (issue_id, stocktake_id, content_hash, created_at,
                 json.dumps(record, ensure_ascii=False, default=str)),
            )
        row = self.get(issue_id)
        return row, "CREATED"

    def get(self, issue_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM discrepancy_issues WHERE issue_id=?", (issue_id,)
            ).fetchone()
        return dict(row) if row else None

    def find_by_stocktake(self, stocktake_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM discrepancy_issues WHERE stocktake_id=?", (stocktake_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_issues(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT issue_id, stocktake_id, content_hash, created_at "
                "FROM discrepancy_issues ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def deserialize(row):
        if row is None:
            return None
        payload = json.loads(row["payload"])
        payload.setdefault("issue_id", row["issue_id"])
        payload.setdefault("issued_at", row["created_at"])
        return payload
