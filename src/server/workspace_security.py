"""Optional signed workspace tokens for multi-user ecommerce deployments.

The default local demo remains anonymous for backward compatibility. A
deployment can set ``ECOMMERCE_WORKSPACE_TOKEN_SECRET`` and
``ECOMMERCE_REQUIRE_WORKSPACE_TOKEN=true`` to turn the workspace header into a
verifiable, expiring boundary. This is an authorization boundary, not a full
identity provider; production deployments should still put the service behind
OIDC/JWT authentication.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def workspace_token_secret() -> str | None:
    value = os.getenv("ECOMMERCE_WORKSPACE_TOKEN_SECRET", "").strip()
    return value or None


def workspace_token_ttl() -> int:
    try:
        return max(300, min(int(os.getenv("ECOMMERCE_WORKSPACE_TOKEN_TTL", "86400")), 7 * 86400))
    except ValueError:
        return 86400


def workspace_token_required() -> bool:
    return os.getenv("ECOMMERCE_REQUIRE_WORKSPACE_TOKEN", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def issue_workspace_token(workspace_id: str, *, secret: str | None = None, now: int | None = None) -> str | None:
    """Issue a short-lived token bound to one workspace identifier."""

    key = secret or workspace_token_secret()
    if not key or not workspace_id:
        return None
    expires_at = int(now if now is not None else time.time()) + workspace_token_ttl()
    payload = _b64(f"v1|{workspace_id}|{expires_at}".encode("utf-8"))
    signature = hmac.new(key.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{_b64(signature)}"


def verify_workspace_token(
    workspace_id: str,
    token: str | None,
    *,
    secret: str | None = None,
    now: int | None = None,
) -> bool:
    """Verify token integrity, workspace binding and expiration."""

    key = secret or workspace_token_secret()
    if not key or not token or token.count(".") != 1:
        return False
    payload, supplied_signature = token.split(".", 1)
    expected_signature = hmac.new(key.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    try:
        valid_signature = hmac.compare_digest(_unb64(supplied_signature), expected_signature)
        version, token_workspace, expires_at = _unb64(payload).decode("utf-8").split("|", 2)
        expires = int(expires_at)
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return False
    current = int(now if now is not None else time.time())
    return valid_signature and version == "v1" and token_workspace == workspace_id and expires >= current


def workspace_auth_mode() -> str:
    if workspace_token_required() and workspace_token_secret():
        return "signed_workspace_token"
    return "anonymous_local"
