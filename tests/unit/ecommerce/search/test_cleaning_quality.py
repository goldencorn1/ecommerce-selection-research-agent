from datetime import datetime, timezone

from src.ecommerce.search.models import SearchResult, clean_search_results
from src.ecommerce.search.quality import classify_source_domain


def _result(url: str, *, title: str = "商品标题", score: float = 0.5) -> SearchResult:
    return SearchResult(
        title=title,
        url=url,
        snippet="  商品   摘要\n",
        source="test",
        score=score,
        retrieved_at=datetime.now(timezone.utc),
    )


def test_clean_search_results_normalizes_and_deduplicates_urls():
    cleaned, telemetry = clean_search_results(
        [
            _result("https://www.example.com/item/?utm_source=test", score=0.4),
            _result("https://example.com/item", score=0.8),
            _result("mock://invalid", title="无效来源"),
        ]
    )

    assert len(cleaned) == 1
    assert cleaned[0].score == 0.8
    assert cleaned[0].url == "https://example.com/item"
    assert telemetry["cleaned_duplicate_count"] == 1
    assert telemetry["cleaned_invalid_url_count"] == 1


def test_source_quality_classifies_common_ecommerce_and_official_domains():
    assert classify_source_domain("item.jd.com").category == "mainland_ecommerce"
    assert classify_source_domain("www.amazon.com").category == "international_ecommerce"
    assert classify_source_domain("store.apple.com").category == "official_brand"
