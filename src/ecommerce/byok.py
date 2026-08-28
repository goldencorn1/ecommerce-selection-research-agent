"""Request-scoped BYOK helpers for the e-commerce workspace.

Secrets are deliberately kept out of the public request payload sent to the
research graph and out of any serializable report/configuration object.
"""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr


def secret_value(value: Any) -> str | None:
    """Return a secret's value for the current request without logging it."""

    if value is None:
        return None
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def runtime_credentials(config: Any | None) -> dict[str, dict[str, str]]:
    """Convert the API request's BYOK block into an internal-only structure."""

    if config is None:
        return {}
    return {
        "model": {
            key: value
            for key, value in {
                "api_key": secret_value(getattr(config, "model_api_key", None)),
                "base_url": secret_value(getattr(config, "model_base_url", None)),
                "model": secret_value(getattr(config, "model_name", None)),
            }.items()
            if value is not None
        },
        "search": {
            "api_key": value
            for key, value in {
                "api_key": secret_value(getattr(config, "search_api_key", None)),
            }.items()
            if value is not None
        },
        "data": {
            "api_key": value
            for key, value in {
                "api_key": secret_value(getattr(config, "data_api_key", None)),
            }.items()
            if value is not None
        },
    }


def scrub_runtime_credentials(credentials: Any) -> None:
    """Best-effort in-place clearing for mutable request-scoped dictionaries."""

    if not isinstance(credentials, dict):
        return
    for value in credentials.values():
        if isinstance(value, dict):
            for key in list(value):
                value[key] = None
            value.clear()
    credentials.clear()
