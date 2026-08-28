"""Strict, optional Bearer JWT authentication for production deployments.

The local demo does not enable this module. Production deployments should
prefer an OIDC gateway that validates RS256/ES256 tokens; this module provides
a small HS256-compatible adapter for controlled single-service deployments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TenantPrincipal:
    subject: str
    tenant_id: str
    scopes: tuple[str, ...]
    issuer: str | None = None


def bearer_auth_required() -> bool:
    return os.getenv("ECOMMERCE_REQUIRE_BEARER_AUTH", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def jwt_secret() -> str | None:
    value = os.getenv("ECOMMERCE_JWT_HS256_SECRET", "").strip()
    return value or None


def jwt_issuer() -> str | None:
    value = os.getenv("ECOMMERCE_JWT_ISSUER", "").strip()
    return value or None


def jwt_audience() -> str | None:
    value = os.getenv("ECOMMERCE_JWT_AUDIENCE", "").strip()
    return value or None


def decode_bearer_token(
    authorization: str | None,
    *,
    secret: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
) -> TenantPrincipal | None:
    """Validate a Bearer JWT with a strict HS256 algorithm and required claims."""

    key = secret or jwt_secret()
    if not key or not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        import jwt

        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=["HS256"],
            issuer=issuer or jwt_issuer(),
            audience=audience or jwt_audience(),
            options={"require": ["exp", "sub", "tenant_id"]},
        )
    except Exception:  # noqa: BLE001 - do not disclose token failure details
        return None
    subject = claims.get("sub")
    tenant_id = claims.get("tenant_id")
    raw_scopes = claims.get("scope", claims.get("scopes", []))
    if not isinstance(subject, str) or not subject.strip():
        return None
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        return None
    if isinstance(raw_scopes, str):
        scopes = tuple(item for item in raw_scopes.split() if item)
    elif isinstance(raw_scopes, list) and all(isinstance(item, str) for item in raw_scopes):
        scopes = tuple(raw_scopes)
    else:
        scopes = ()
    return TenantPrincipal(
        subject=subject,
        tenant_id=tenant_id,
        scopes=scopes,
        issuer=claims.get("iss") if isinstance(claims.get("iss"), str) else None,
    )
