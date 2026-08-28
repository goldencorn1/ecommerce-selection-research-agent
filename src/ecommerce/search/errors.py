"""Structured errors raised by search providers."""

from __future__ import annotations

from typing import Any


class SearchProviderError(RuntimeError):
    """Base error with a stable machine-readable code and safe details."""

    code = "search_provider_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Return safe diagnostics without exposing API keys or request headers."""

        return {"code": self.code, "message": self.message, "details": self.details}


class SearchConfigurationError(SearchProviderError):
    """The provider cannot run because its endpoint or API key is missing."""

    code = "search_configuration_error"


class SearchTimeoutError(SearchProviderError):
    """The provider did not respond before the configured timeout."""

    code = "search_timeout"


class SearchHTTPError(SearchProviderError):
    """The provider returned a non-success HTTP status."""

    code = "search_http_error"

    def __init__(self, status_code: int, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            f"Search provider returned HTTP {status_code}",
            details={"status_code": status_code, **(details or {})},
        )
        self.status_code = status_code


class SearchResponseError(SearchProviderError):
    """The provider response was not valid JSON or had an invalid shape."""

    code = "search_response_error"


class SearchEmptyResultError(SearchProviderError):
    """The provider responded successfully but returned no usable results."""

    code = "search_empty_result"
