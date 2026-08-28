"""Strict OIDC/JWKS Bearer token verification for D4 deployments.

The demo keeps the D3 HS256 adapter as the default.  OIDC mode is opt-in and
requires an issuer, audience, HTTPS JWKS URL (or loopback HTTP for local
tests), and an explicit algorithm allowlist limited to RS256/ES256.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse
from typing import Any, Callable

from src.server.tenant_auth import TenantPrincipal, bearer_auth_required

OIDC_ALLOWED_ALGORITHMS = frozenset({"RS256", "ES256"})


def oidc_provider_enabled() -> bool:
    return bearer_auth_required() and os.getenv(
        "ECOMMERCE_BEARER_PROVIDER", "hs256"
    ).strip().lower() == "oidc"


def oidc_issuer() -> str | None:
    value = os.getenv("ECOMMERCE_OIDC_ISSUER", "").strip()
    return value or None


def oidc_audience() -> str | None:
    value = os.getenv("ECOMMERCE_OIDC_AUDIENCE", "").strip()
    return value or None


def oidc_jwks_url() -> str | None:
    value = os.getenv("ECOMMERCE_OIDC_JWKS_URL", "").strip()
    return value or None


def oidc_algorithms() -> tuple[str, ...]:
    raw = os.getenv("ECOMMERCE_OIDC_ALGORITHMS", "RS256")
    values = tuple(item.strip().upper() for item in raw.split(",") if item.strip())
    if not values or any(item not in OIDC_ALLOWED_ALGORITHMS for item in values):
        return ()
    return tuple(dict.fromkeys(values))


def oidc_auth_configured() -> bool:
    url = oidc_jwks_url()
    if not oidc_issuer() or not oidc_audience() or not url or not oidc_algorithms():
        return False
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return True
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}


def _principal_from_claims(claims: dict[str, Any]) -> TenantPrincipal | None:
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
    issuer = claims.get("iss")
    return TenantPrincipal(
        subject=subject,
        tenant_id=tenant_id,
        scopes=scopes,
        issuer=issuer if isinstance(issuer, str) else None,
    )


def decode_oidc_bearer_token(
    authorization: str | None,
    *,
    jwks_url: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    algorithms: tuple[str, ...] | None = None,
    jwks_client_factory: Callable[[str], Any] | None = None,
) -> TenantPrincipal | None:
    """Validate an OIDC JWT using a remote JWKS signing key.

    The client factory is injectable only for deterministic tests; production
    uses PyJWT's JWKS client and never accepts a key supplied by the request.
    """

    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    selected_url = jwks_url or oidc_jwks_url()
    selected_issuer = issuer or oidc_issuer()
    selected_audience = audience or oidc_audience()
    selected_algorithms = algorithms or oidc_algorithms()
    if not token or not selected_url or not selected_issuer or not selected_audience:
        return None
    if not selected_algorithms or any(
        item not in OIDC_ALLOWED_ALGORITHMS for item in selected_algorithms
    ):
        return None
    parsed = urlparse(selected_url)
    if not (
        parsed.scheme == "https" and parsed.netloc
        or parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
    ):
        return None
    try:
        import jwt

        factory = jwks_client_factory or jwt.PyJWKClient
        signing_key = factory(selected_url).get_signing_key_from_jwt(token).key
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key,
            algorithms=list(selected_algorithms),
            issuer=selected_issuer,
            audience=selected_audience,
            options={"require": ["exp", "sub", "tenant_id", "iss", "aud"]},
        )
    except Exception:  # noqa: BLE001 - do not disclose token/JWKS failures
        return None
    return _principal_from_claims(claims)
