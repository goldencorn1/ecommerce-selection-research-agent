"""Common search contracts and conversion helpers.

Search results should be collected only from sources the caller is permitted
to access. Public availability does not remove obligations to respect robots
directives, copyright, privacy law, rate limits, or service terms. Keep
personal or confidential query data out of third-party search requests.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Protocol, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid5, NAMESPACE_URL

from ..models import Evidence


_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_",
}


def normalize_search_url(url: str) -> str:
    """Return a stable URL suitable for result de-duplication."""

    clean_url = url.strip()
    parsed = urlsplit(clean_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return clean_url
    hostname = parsed.hostname.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    netloc = hostname
    try:
        port = parsed.port
    except ValueError:
        return clean_url
    if port is not None:
        netloc = f"{hostname}:{port}"
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_QUERY_KEYS and not key.lower().startswith("utm_")
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path.rstrip("/") or "/",
            urlencode(sorted(query)),
            "",
        )
    )


def clean_search_results(
    results: Sequence[SearchResult],
) -> tuple[list[SearchResult], dict[str, int]]:
    """Normalize, de-duplicate and remove unusable search results."""

    accepted: dict[str, SearchResult] = {}
    invalid_url_count = 0
    empty_title_count = 0
    duplicate_count = 0
    for result in results:
        canonical = result.canonical_url
        if not canonical.startswith(("http://", "https://")):
            invalid_url_count += 1
            continue
        title = " ".join(result.title.split())
        snippet = " ".join(result.snippet.split())
        if not title:
            empty_title_count += 1
            continue
        normalized = replace(result, title=title, snippet=snippet or title, url=canonical)
        previous = accepted.get(canonical)
        if previous is not None:
            duplicate_count += 1
            current_key = (normalized.score, normalized.price is not None, normalized.published_at is not None)
            previous_key = (previous.score, previous.price is not None, previous.published_at is not None)
            if current_key <= previous_key:
                continue
        accepted[canonical] = normalized
    return list(accepted.values()), {
        "cleaned_invalid_url_count": invalid_url_count,
        "cleaned_empty_title_count": empty_title_count,
        "cleaned_duplicate_count": duplicate_count,
        "cleaned_result_count": len(accepted),
    }


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A normalized result returned by any search provider."""

    title: str
    url: str
    snippet: str
    source: str
    score: float
    retrieved_at: datetime
    published_at: datetime | None = None
    price: float | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("SearchResult.title must not be empty")
        if not self.url.strip():
            raise ValueError("SearchResult.url must not be empty")
        if not self.source.strip():
            raise ValueError("SearchResult.source must not be empty")
        if not 0 <= self.score <= 1:
            raise ValueError("SearchResult.score must be between 0 and 1")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("SearchResult.retrieved_at must be timezone-aware")
        if self.published_at is not None and self.published_at.tzinfo is None:
            raise ValueError("SearchResult.published_at must be timezone-aware")
        if self.price is not None and self.price < 0:
            raise ValueError("SearchResult.price must be non-negative")

    @property
    def canonical_url(self) -> str:
        """Return a tracking-parameter-free URL for identity comparisons."""

        return normalize_search_url(self.url)

    @property
    def domain(self) -> str:
        """Return the normalized hostname for lightweight source statistics."""

        return (urlsplit(self.canonical_url).hostname or "").lower()

    @property
    def content(self) -> str:
        """Alias retained for providers that call the text field content."""

        return self.snippet


@dataclass(frozen=True, slots=True)
class SearchResponse:
    """Results plus metadata belonging to one provider call."""

    results: tuple[SearchResult, ...]
    metadata: dict[str, int | float | bool | str | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", tuple(self.results))
        object.__setattr__(self, "metadata", dict(self.metadata))


class SearchProvider(Protocol):
    """Minimal synchronous contract used by the e-commerce workflow."""

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """Return normalized results or raise a ``SearchProviderError``."""


class SearchProviderWithMetadata(Protocol):
    """Optional extension for callers that need per-call diagnostics."""

    def search_with_metadata(
        self, query: str, *, max_results: int = 5
    ) -> SearchResponse:
        """Return results and metadata from the same logical request."""


def search_result_to_evidence(
    result: SearchResult,
    *,
    evidence_id: str | None = None,
    supports: Sequence[str] = (),
) -> Evidence:
    """Map one normalized result into the MVP's existing ``Evidence`` model.

    The provider source is preserved in ``Evidence.source`` and the URL stays
    traceable through the deterministic evidence ID. The score is treated as
    retrieval confidence only; it is not a claim about factual truth.
    """

    stable_id = evidence_id or f"search-{uuid5(NAMESPACE_URL, result.canonical_url)}"
    summary = result.snippet.strip() or result.title.strip()
    return Evidence(
        evidence_id=stable_id,
        # Evidence.source is the auditable source locator. Keep the provider
        # label available through SearchResult.source/source_type instead of
        # replacing the URL needed by provenance validation.
        source=result.url,
        title=result.title.strip(),
        summary=summary,
        confidence=result.score,
        supports=list(supports),
        retrieved_at=result.retrieved_at,
        source_type=result.source,
    )


def utc_now() -> datetime:
    """Return an aware UTC timestamp, kept as a seam for deterministic tests."""

    return datetime.now(timezone.utc)
