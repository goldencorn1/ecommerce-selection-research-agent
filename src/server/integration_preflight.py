"""Secret-safe D5 readiness checks for real environment integration.

The default path is a no-network plan.  Explicit execution may probe only the
configured OIDC JWKS endpoint, PostgreSQL DSN and user-provided authorized
data file; values and provider error details are never returned.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.ecommerce.authorized_data import (
    AuthorizedDataSource,
    AuthorizedProductRecord,
    validate_authorized_dataset,
)
from src.server.oidc_auth import oidc_auth_configured, oidc_jwks_url


def _env_present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _check(status: str, check_id: str, message: str, *, required: tuple[str, ...]) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "message": message,
        "required_env": list(required),
    }


def build_d5_preflight_plan() -> dict[str, Any]:
    checks = [
        _check(
            "ready" if oidc_auth_configured() else "blocked",
            "oidc_jwks",
            "OIDC issuer、audience、JWKS URL 和算法白名单已配置"
            if oidc_auth_configured()
            else "等待正式 OIDC/JWKS 配置",
            required=(
                "ECOMMERCE_REQUIRE_BEARER_AUTH",
                "ECOMMERCE_BEARER_PROVIDER",
                "ECOMMERCE_OIDC_ISSUER",
                "ECOMMERCE_OIDC_AUDIENCE",
                "ECOMMERCE_OIDC_JWKS_URL",
            ),
        ),
        _check(
            "ready"
            if _env_present("ECOMMERCE_POSTGRES_DSN") or _env_present("DATABASE_URL")
            else "blocked",
            "postgresql_rls",
            "PostgreSQL DSN 已提供，可进行 RLS 联调"
            if (_env_present("ECOMMERCE_POSTGRES_DSN") or _env_present("DATABASE_URL"))
            else "等待 PostgreSQL DSN",
            required=("ECOMMERCE_POSTGRES_DSN", "DATABASE_URL"),
        ),
        _check(
            "ready" if _env_present("ECOMMERCE_AUTHORIZED_DATA_FILE") else "blocked",
            "authorized_data",
            "用户授权数据文件已指定，可进行逐条数据校验"
            if _env_present("ECOMMERCE_AUTHORIZED_DATA_FILE")
            else "等待用户自有且有授权的数据文件",
            required=("ECOMMERCE_AUTHORIZED_DATA_FILE",),
        ),
    ]
    blocking_reasons = [item["message"] for item in checks if item["status"] != "ready"]
    return {
        "schema_version": "d5-integration-preflight-v1",
        "mode": "real-environment",
        "network_requested": False,
        "status": "ready" if not blocking_reasons else "blocked",
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "commercial_decision_ready": False,
        "next_step": (
            "所有检查通过后，显式执行 D5 联调；当前不代表真实身份、数据库或商品数据已接通。"
        ),
    }


def _load_authorized_data(path: Path) -> tuple[AuthorizedDataSource, list[AuthorizedProductRecord]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = AuthorizedDataSource.model_validate(payload["source"])
    records = [AuthorizedProductRecord.model_validate(item) for item in payload["records"]]
    return source, records


def _probe_jwks() -> dict[str, Any]:
    import httpx

    url = oidc_jwks_url()
    if not url:
        return {"status": "blocked", "message": "OIDC/JWKS 配置不完整"}
    try:
        response = httpx.get(url, timeout=5.0, follow_redirects=False)
        payload = response.json() if response.status_code == 200 else {}
        valid = isinstance(payload, dict) and isinstance(payload.get("keys"), list)
        return {
            "status": "ready" if response.status_code == 200 and valid else "blocked",
            "message": "JWKS 响应可解析" if response.status_code == 200 and valid else "JWKS 响应不可用",
            "http_status": response.status_code,
        }
    except Exception:  # noqa: BLE001 - do not expose provider/network details
        return {"status": "blocked", "message": "JWKS 请求失败"}


def _probe_postgres() -> dict[str, Any]:
    dsn = os.getenv("ECOMMERCE_POSTGRES_DSN", "").strip() or os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        return {"status": "blocked", "message": "PostgreSQL DSN 未配置"}
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return {"status": "ready", "message": "PostgreSQL 可连接"}
    except Exception:  # noqa: BLE001 - never return DSN or driver details
        return {"status": "blocked", "message": "PostgreSQL 连接失败"}


def execute_d5_preflight(*, now=None) -> dict[str, Any]:
    """Explicitly probe configured dependencies without exposing credentials."""

    plan = build_d5_preflight_plan()
    checks = {item["id"]: dict(item) for item in plan["checks"]}
    checks["oidc_jwks"].update(_probe_jwks())
    checks["postgresql_rls"].update(_probe_postgres())
    data_path = os.getenv("ECOMMERCE_AUTHORIZED_DATA_FILE", "").strip()
    if not data_path:
        checks["authorized_data"].update(
            {"status": "blocked", "message": "授权数据文件未配置"}
        )
    else:
        try:
            source, records = _load_authorized_data(Path(data_path))
            checks["authorized_data"].update(
                validate_authorized_dataset(source, records, now=now)
            )
            checks["authorized_data"]["status"] = (
                "ready" if checks["authorized_data"].get("status") == "ready_for_verification" else "blocked"
            )
        except Exception:  # noqa: BLE001 - keep file/provider errors secret-safe
            checks["authorized_data"].update(
                {"status": "blocked", "message": "授权数据文件无法校验"}
            )
    blocking_reasons = [
        item.get("message", "检查未通过")
        for item in checks.values()
        if item.get("status") != "ready"
    ]
    return {
        "schema_version": "d5-integration-preflight-v1",
        "mode": "real-environment",
        "network_requested": True,
        "status": "ready" if not blocking_reasons else "blocked",
        "checks": list(checks.values()),
        "blocking_reasons": blocking_reasons,
        "commercial_decision_ready": False,
        "next_step": "仅当 status=ready 时，才可显式运行授权数据下的跨品类评测。",
    }
