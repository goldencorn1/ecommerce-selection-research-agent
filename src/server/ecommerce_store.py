"""Small local report store for the interactive ecommerce workspace.

SQLite is deliberately used as the local default so the demo has persistence
without requiring a database service.  D4 adds an explicit ``tenant_id``
column while retaining ``owner_id`` as a compatibility alias for existing
callers and old demo databases.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


def _default_db_path() -> Path:
    configured = os.getenv("ECOMMERCE_HISTORY_DB")
    if configured:
        return Path(configured)
    return Path("artifacts/ecommerce/web-history.sqlite3")


class EcommerceReportStore:
    """Persist report payloads and expose deterministic history operations."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ecommerce_reports (
                    report_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    market TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    average_score REAL NOT NULL,
                    recommendation_count INTEGER NOT NULL,
                    candidate_count INTEGER NOT NULL,
                    search_status TEXT NOT NULL,
                    model_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(ecommerce_reports)"
                ).fetchall()
            }
            if "tenant_id" not in columns:
                connection.execute(
                    "ALTER TABLE ecommerce_reports ADD COLUMN tenant_id TEXT"
                )
                connection.execute(
                    "UPDATE ecommerce_reports SET tenant_id = owner_id "
                    "WHERE tenant_id IS NULL OR tenant_id = ''"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ecommerce_reports_owner_time "
                "ON ecommerce_reports(owner_id, created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ecommerce_reports_tenant_time "
                "ON ecommerce_reports(tenant_id, created_at DESC)"
            )

    @staticmethod
    def _summary(payload: dict[str, Any]) -> tuple[str, str, float, int, int, str, str]:
        report = payload.get("report", {})
        recommendations = report.get("recommendations", [])
        scores = [float(item.get("score", {}).get("total", 0)) for item in recommendations]
        catalog = payload.get("candidate_catalog", {})
        request = report.get("request", {})
        return (
            str(request.get("category", "")),
            str(request.get("target_market", request.get("market", ""))),
            round(sum(scores) / len(scores), 4) if scores else 0.0,
            len(recommendations),
            len(catalog.get("candidates", [])),
            str(payload.get("search_status", "not_used")),
            str(payload.get("model_status", "not_used")),
        )

    def save(
        self,
        payload: dict[str, Any],
        *,
        owner_id: str = "local-user",
        tenant_id: str | None = None,
    ) -> str:
        tenant = tenant_id or owner_id or "local-user"
        report_id = str(payload.get("history_id") or uuid4())
        category, market, average, recommendation_count, candidate_count, search_status, model_status = self._summary(payload)
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO ecommerce_reports
                (report_id, tenant_id, owner_id, category, market, created_at, average_score,
                 recommendation_count, candidate_count, search_status, model_status, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    tenant,
                    tenant,
                    category,
                    market,
                    created_at,
                    average,
                    recommendation_count,
                    candidate_count,
                    search_status,
                    model_status,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
        return report_id

    @staticmethod
    def _row_summary(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "history_id": row["report_id"],
            "tenant_id": row["tenant_id"],
            "owner_id": row["owner_id"],
            "category": row["category"],
            "market": row["market"],
            "created_at": row["created_at"],
            "average_score": row["average_score"],
            "recommendation_count": row["recommendation_count"],
            "candidate_count": row["candidate_count"],
            "search_status": row["search_status"],
            "model_status": row["model_status"],
        }

    def list(
        self,
        *,
        owner_id: str = "local-user",
        tenant_id: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        tenant = tenant_id or owner_id or "local-user"
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ecommerce_reports WHERE tenant_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (tenant, max(1, min(limit, 100))),
            ).fetchall()
        return [self._row_summary(row) for row in rows]

    def get(
        self,
        report_id: str,
        *,
        owner_id: str = "local-user",
        tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        tenant = tenant_id or owner_id or "local-user"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ecommerce_reports WHERE report_id = ? AND tenant_id = ?",
                (report_id, tenant),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        payload["history_id"] = row["report_id"]
        payload["history"] = self._row_summary(row)
        return payload

    def compare(
        self,
        report_ids: list[str],
        *,
        owner_id: str = "local-user",
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        tenant = tenant_id or owner_id or "local-user"
        rows: list[dict[str, Any]] = []
        with self._connect() as connection:
            for report_id in report_ids:
                row = connection.execute(
                    "SELECT * FROM ecommerce_reports WHERE report_id = ? AND tenant_id = ?",
                    (report_id, tenant),
                ).fetchone()
                if row is not None:
                    rows.append(self._row_summary(row))
        return {
            "status": "success" if rows else "empty",
            "requested_count": len(report_ids),
            "matched_count": len(rows),
            "rows": rows,
        }
