"""Deterministic offline search provider for demos and unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import SearchResult, SearchProvider


_MOCK_RETRIEVED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class MockSearchProvider(SearchProvider):
    """Return stable synthetic results without network access or credentials."""

    source: str = "mock-search"

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """Generate repeatable results for a query.

        Synthetic content must not be presented as market evidence. It exists
        only to exercise the workflow before an authorized provider is wired.
        """

        if max_results < 1:
            return []
        clean_query = " ".join(query.split()) or "未命名品类"
        return [
            SearchResult(
                title=f"{clean_query} Mock 结果 {index}",
                url=f"https://mock.invalid/search/{index}",
                snippet=f"这是关于“{clean_query}”的离线模拟搜索摘要 {index}。",
                source=self.source,
                score=round(max(0.1, 0.95 - index * 0.08), 2),
                # A fixed synthetic timestamp keeps complete mock results
                # reproducible; it is not a claim about live retrieval time.
                retrieved_at=_MOCK_RETRIEVED_AT,
            )
            for index in range(1, max_results + 1)
        ]
