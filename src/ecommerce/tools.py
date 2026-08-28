"""Price and ranking tool contracts for the A2 e-commerce boundary.

The HTTP adapters deliberately accept their transport or client from the
caller.  This keeps unit tests offline and makes authentication a concern of
the application that wires the adapter, rather than this module.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Protocol, Sequence
from uuid import NAMESPACE_URL, uuid5

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .models import Evidence


class ToolError(RuntimeError):
    """Base error with a stable code and safe, serializable details."""

    code = "tool_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ToolConfigurationError(ToolError):
    """The adapter was configured with unusable request settings."""

    code = "tool_configuration_error"


class ToolTimeoutError(ToolError):
    """The provider did not respond within the configured timeout."""

    code = "tool_timeout"


class ToolHTTPError(ToolError):
    """The provider returned a non-success HTTP status or transport error."""

    code = "tool_http_error"

    def __init__(
        self, status_code: int, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            f"Tool provider returned HTTP {status_code}",
            details={"status_code": status_code, **(details or {})},
        )
        self.status_code = status_code


class ToolResponseError(ToolError):
    """The provider response was not valid JSON or had the wrong shape."""

    code = "tool_response_error"


class ToolEmptyResultError(ToolError):
    """Optional error for callers that choose to treat an empty result as fatal."""

    code = "tool_empty_result"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_evidence_id(prefix: str, source: str, identity: str) -> str:
    return f"{prefix}-{uuid5(NAMESPACE_URL, f'{source}|{identity}')}"


class _ToolResult(BaseModel):
    """Shared provenance fields carried by every tool result."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(default="unknown", min_length=1)
    retrieved_at: datetime = Field(default_factory=_utc_now)
    evidence_id: str | None = Field(default=None, min_length=1)
    supports: list[str] = Field(default_factory=list)
    source_type: str = Field(default="unknown", min_length=1)
    confidence: float = Field(default=1.0, ge=0, le=1)

    def _evidence(
        self,
        *,
        title: str,
        summary: str,
        prefix: str,
        identity: str,
        supports: Sequence[str] | None = None,
    ) -> Evidence:
        merged_supports = list(dict.fromkeys([*self.supports, *(supports or ())]))
        evidence_id = self.evidence_id or _stable_evidence_id(
            prefix, self.source, identity
        )
        return Evidence(
            evidence_id=evidence_id,
            source=self.source,
            title=title,
            summary=summary,
            confidence=self.confidence,
            supports=merged_supports,
            retrieved_at=self.retrieved_at,
            source_type=self.source_type,
        )


class PriceQuote(_ToolResult):
    """One normalized price observation."""

    price: float = Field(ge=0)
    product_id: str = ""
    title: str = "价格报价"
    currency: str = Field(default="CNY", min_length=1)

    def to_evidence(self, *, supports: Sequence[str] | None = None) -> Evidence:
        label = self.title or self.product_id or "价格报价"
        summary = f"{label}: {self.currency} {self.price:.2f}"
        return self._evidence(
            title=label,
            summary=summary,
            prefix="price",
            identity=self.product_id or label,
            supports=supports,
        )

    def as_evidence(self, *, supports: Sequence[str] | None = None) -> Evidence:
        """Alias for callers that use an ``as_*`` conversion convention."""

        return self.to_evidence(supports=supports)


class RankEntry(_ToolResult):
    """One normalized product entry from a category ranking."""

    rank: int = Field(ge=1)
    product_id: str = ""
    title: str = "榜单条目"
    score: float | None = Field(default=None, ge=0)

    def to_evidence(self, *, supports: Sequence[str] | None = None) -> Evidence:
        label = self.title or self.product_id or "榜单条目"
        summary = f"榜单第 {self.rank} 名：{label}"
        if self.score is not None:
            summary += f"（score={self.score:g}）"
        return self._evidence(
            title=label,
            summary=summary,
            prefix="rank",
            identity=self.product_id or f"{self.rank}:{label}",
            supports=supports,
        )

    def as_evidence(self, *, supports: Sequence[str] | None = None) -> Evidence:
        """Alias for callers that use an ``as_*`` conversion convention."""

        return self.to_evidence(supports=supports)


def price_to_evidence(
    quote: PriceQuote, *, supports: Sequence[str] | None = None
) -> Evidence:
    """Convert a price quote while retaining all provenance fields."""

    return quote.to_evidence(supports=supports)


def rank_to_evidence(
    entry: RankEntry, *, supports: Sequence[str] | None = None
) -> Evidence:
    """Convert a ranking entry while retaining all provenance fields."""

    return entry.to_evidence(supports=supports)


class PriceTool(Protocol):
    """Minimal synchronous price lookup contract."""

    def get_price(self, query: str) -> list[PriceQuote]:
        """Return price observations or an empty list when no data is available."""


class RankTool(Protocol):
    """Minimal synchronous category ranking contract."""

    def get_rankings(self, category: str, *, limit: int = 10) -> list[RankEntry]:
        """Return ranking observations or an empty list when no data is available."""


_MOCK_RETRIEVED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _slug(value: str) -> str:
    return (
        re.sub(r"[^\w\-]+", "-", value.strip(), flags=re.UNICODE).strip("-") or "query"
    )


class MockPriceTool:
    """Stable offline price tool; it never reads credentials or uses a network."""

    def __init__(
        self,
        quotes: Sequence[PriceQuote] | None = None,
        *,
        empty_results: bool = False,
    ) -> None:
        self._quotes = tuple(quotes) if quotes is not None else None
        self.empty_results = empty_results

    def get_price(self, query: str) -> list[PriceQuote]:
        if self.empty_results or not query.strip():
            return []
        if self._quotes is not None:
            return list(self._quotes)
        clean_query = " ".join(query.split())
        slug = _slug(clean_query)
        return [
            PriceQuote(
                product_id=f"mock-{slug}",
                title=f"{clean_query} Mock 报价",
                price=129.0,
                currency="CNY",
                source=f"mock://price/{slug}",
                retrieved_at=_MOCK_RETRIEVED_AT,
                evidence_id=f"mock-price-{slug}",
                supports=["price-band"],
                source_type="mock",
                confidence=0.5,
            )
        ]

    def quote(self, query: str) -> list[PriceQuote]:
        return self.get_price(query)


class MockRankTool:
    """Stable offline ranking tool; it never reads credentials or uses a network."""

    def __init__(
        self,
        entries: Sequence[RankEntry] | None = None,
        *,
        empty_results: bool = False,
    ) -> None:
        self._entries = tuple(entries) if entries is not None else None
        self.empty_results = empty_results

    def get_rankings(self, category: str, *, limit: int = 10) -> list[RankEntry]:
        if self.empty_results or not category.strip() or limit < 1:
            return []
        if self._entries is not None:
            return list(self._entries[:limit])
        clean_category = " ".join(category.split())
        slug = _slug(clean_category)
        return [
            RankEntry(
                rank=index,
                product_id=f"mock-{slug}-{index}",
                title=f"{clean_category} Mock 榜单 {index}",
                score=1.0 - (index - 1) * 0.1,
                source=f"mock://rank/{slug}",
                retrieved_at=_MOCK_RETRIEVED_AT,
                evidence_id=f"mock-rank-{slug}-{index}",
                supports=["ranking"],
                source_type="mock",
                confidence=0.5,
            )
            for index in range(1, min(limit, 3) + 1)
        ]

    def rank(self, category: str, *, limit: int = 10) -> list[RankEntry]:
        return self.get_rankings(category, limit=limit)


def _parse_retrieved_at(value: Any) -> datetime:
    if value is None:
        return _utc_now()
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ToolResponseError(
                "Tool response contained an invalid retrieved_at"
            ) from exc
    else:
        raise ToolResponseError("Tool response contained an invalid retrieved_at")
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _as_items(body: Any, keys: Sequence[str]) -> list[Any]:
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        raise ToolResponseError("Tool response must be a JSON object or array")
    candidates: list[Any] = [body]
    if "data" in body:
        candidates.insert(0, body["data"])
    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, dict):
            for key in keys:
                if isinstance(candidate.get(key), list):
                    return candidate[key]
            if isinstance(candidate.get("items"), list):
                return candidate["items"]
    raise ToolResponseError(f"Tool response must contain one of: {', '.join(keys)}")


def _value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) else fallback


def _number(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ToolResponseError(f"Tool response field {field_name} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ToolResponseError(
            f"Tool response field {field_name} must be numeric"
        ) from exc
    if parsed < 0:
        raise ToolResponseError(
            f"Tool response field {field_name} must be non-negative"
        )
    return parsed


def _supports(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ToolResponseError("Tool response field supports must be a string array")
    return value


class _HTTPTool:
    """Shared dependency-injected HTTP request implementation."""

    endpoint: str
    timeout: float
    transport: Any | None
    client: Any | None
    headers: dict[str, str]

    def _request(self, params: dict[str, Any]) -> Any:
        if not self.endpoint.strip():
            raise ToolConfigurationError("Tool endpoint must not be empty")
        if self.timeout <= 0:
            raise ToolConfigurationError("Tool timeout must be positive")
        owned = self.client is None
        request_client = (
            httpx.Client(
                transport=self.transport, timeout=self.timeout, headers=self.headers
            )
            if owned
            else self.client
        )
        try:
            if hasattr(request_client, "get"):
                response = request_client.get(self.endpoint, params=params)
            else:
                response = request_client.request("GET", self.endpoint, params=params)
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ToolTimeoutError("Tool request timed out") from exc
        except httpx.HTTPError as exc:
            raise ToolHTTPError(0, details={"error_type": type(exc).__name__}) from exc
        except Exception as exc:
            raise ToolHTTPError(0, details={"error_type": type(exc).__name__}) from exc
        finally:
            if owned:
                request_client.close()
        if not 200 <= response.status_code < 300:
            raise ToolHTTPError(response.status_code)
        try:
            return response.json()
        except (TypeError, ValueError) as exc:
            raise ToolResponseError("Tool response was not valid JSON") from exc


class HTTPPriceTool(_HTTPTool):
    """GET a standard JSON price response using an injected HTTP seam."""

    def __init__(
        self,
        endpoint: str = "https://api.example.invalid/prices",
        *,
        timeout: float = 10.0,
        transport: Any | None = None,
        client: Any | None = None,
        headers: dict[str, str] | None = None,
        source_type: str = "http",
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.transport = transport
        self.client = client
        self.headers = dict(headers or {})
        self.source_type = source_type

    def get_price(self, query: str) -> list[PriceQuote]:
        if not query.strip():
            return []
        body = self._request({"query": query.strip()})
        items = _as_items(body, ("quotes", "prices", "results"))
        result: list[PriceQuote] = []
        for item in items:
            if not isinstance(item, dict):
                raise ToolResponseError("Each price quote must be a JSON object")
            product_id = _text(_value(item, "product_id", "id", "sku"))
            title = _text(
                _value(item, "title", "name", "product_name"), product_id or "价格报价"
            )
            source = _text(_value(item, "source", "url"), self.endpoint)
            price_value = _value(item, "price", "amount", "value")
            if isinstance(price_value, dict):
                price_value = _value(price_value, "amount", "value")
            try:
                quote = PriceQuote(
                    product_id=product_id,
                    title=title,
                    price=_number(price_value, field_name="price"),
                    currency=_text(_value(item, "currency", "currency_code"), "CNY"),
                    source=source,
                    retrieved_at=_parse_retrieved_at(
                        _value(item, "retrieved_at", "fetched_at", "timestamp")
                    ),
                    evidence_id=_text(_value(item, "evidence_id")) or None,
                    supports=_supports(item.get("supports")),
                    source_type=_text(item.get("source_type"), self.source_type),
                    confidence=_number(
                        item.get("confidence", 1.0), field_name="confidence"
                    ),
                )
            except ToolError:
                raise
            except ValueError as exc:
                raise ToolResponseError(
                    "Tool response contained an invalid price quote"
                ) from exc
            result.append(quote)
        return result

    def quote(self, query: str) -> list[PriceQuote]:
        return self.get_price(query)


class HTTPRankTool(_HTTPTool):
    """GET a standard JSON ranking response using an injected HTTP seam."""

    def __init__(
        self,
        endpoint: str = "https://api.example.invalid/rankings",
        *,
        timeout: float = 10.0,
        transport: Any | None = None,
        client: Any | None = None,
        headers: dict[str, str] | None = None,
        source_type: str = "http",
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.transport = transport
        self.client = client
        self.headers = dict(headers or {})
        self.source_type = source_type

    def get_rankings(self, category: str, *, limit: int = 10) -> list[RankEntry]:
        if not category.strip() or limit < 1:
            return []
        body = self._request({"category": category.strip(), "limit": limit})
        items = _as_items(body, ("rankings", "ranks", "entries", "results"))
        result: list[RankEntry] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                raise ToolResponseError("Each ranking entry must be a JSON object")
            product_id = _text(_value(item, "product_id", "id", "sku"))
            title = _text(
                _value(item, "title", "name", "product_name"), product_id or "榜单条目"
            )
            source = _text(_value(item, "source", "url"), self.endpoint)
            rank_value = _value(item, "rank", "position")
            try:
                rank = int(rank_value)
            except (TypeError, ValueError) as exc:
                raise ToolResponseError(
                    "Tool response field rank must be an integer"
                ) from exc
            if rank < 1:
                raise ToolResponseError("Tool response field rank must be positive")
            score_value = _value(item, "score", "rating")
            try:
                entry = RankEntry(
                    rank=rank,
                    product_id=product_id,
                    title=title,
                    score=None
                    if score_value is None
                    else _number(score_value, field_name="score"),
                    source=source,
                    retrieved_at=_parse_retrieved_at(
                        _value(item, "retrieved_at", "fetched_at", "timestamp")
                    ),
                    evidence_id=_text(_value(item, "evidence_id")) or None,
                    supports=_supports(item.get("supports")),
                    source_type=_text(item.get("source_type"), self.source_type),
                    confidence=_number(
                        item.get("confidence", 1.0), field_name="confidence"
                    ),
                )
            except ToolError:
                raise
            except ValueError as exc:
                raise ToolResponseError(
                    "Tool response contained an invalid ranking entry"
                ) from exc
            result.append(entry)
        return result

    def rank(self, category: str, *, limit: int = 10) -> list[RankEntry]:
        return self.get_rankings(category, limit=limit)


__all__ = [
    "HTTPPriceTool",
    "HTTPRankTool",
    "MockPriceTool",
    "MockRankTool",
    "PriceQuote",
    "PriceTool",
    "RankEntry",
    "RankTool",
    "ToolConfigurationError",
    "ToolEmptyResultError",
    "ToolError",
    "ToolHTTPError",
    "ToolResponseError",
    "ToolTimeoutError",
    "price_to_evidence",
    "rank_to_evidence",
]
