from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from src.ecommerce_graph import run_ecommerce_graph
from src.ecommerce.models import EcommerceResearchRequest
from src.ecommerce.providers import SearchBackedResearchProvider
from src.ecommerce.search import SearchResult


def _search_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "results": [
                {
                    "title": "授权搜索结果",
                    "url": "https://example.test/result",
                    "content": "公开摘要，售价 ¥169，供离线集成测试使用。",
                    "score": 0.9,
                    "published_date": "2026-08-01T12:00:00Z",
                }
            ]
        },
    )


def test_search_provider_is_connected_to_graph_with_injected_transport():
    provider = __import__(
        "src.ecommerce.search", fromlist=["HttpJsonSearchProvider"]
    ).HttpJsonSearchProvider(
        api_key="unit-test-key",
        transport=httpx.MockTransport(_search_handler),
    )
    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "search_enabled": True,
            "search_provider": provider,
        }
    )

    assert state["ecommerce_metrics"]["mode"] == "search"
    assert state["ecommerce_metrics"]["external_request_count"] == 4
    assert state["ecommerce_search_status"] == "success"
    assert state["ecommerce_metrics"]["overall_status"] == "success"
    assert set(state["ecommerce_search_details"]) == {"market", "competitor", "customer", "opportunity"}
    assert state["ecommerce_report"]["evidence"]
    assert state["ecommerce_report"]["evidence"][0]["source"] == "https://example.test/result"
    assert state["ecommerce_report"]["evidence"][0]["source_type"] == "tavily"
    assert state["ecommerce_report"]["evidence"][0]["retrieved_at"]
    assert len(state["ecommerce_report"]["evidence"]) == 1
    assert set(state["ecommerce_report"]["evidence"][0]["supports"]) == {
        "search:market",
        "search:competitor",
        "search:customer",
        "search:opportunity",
    }
    assert state["ecommerce_report"]["competitors"][0]["price"] == 169.0
    assert state["ecommerce_report"]["competitors"][0]["price_source"] == "explicit"


def test_search_queries_prioritize_product_and_usage_signals():
    queries: list[str] = []

    class CapturingProvider:
        request_count = 0

        def search(self, query: str, *, max_results: int = 5):
            queries.append(query)
            self.request_count += 1
            now = datetime.now(timezone.utc)
            return [
                SearchResult(
                    title="授权商品结果",
                    url=f"https://example.test/{self.request_count}",
                    snippet="售价 ¥129，用户评价提到稳定承重。",
                    source="unit",
                    score=0.9,
                    retrieved_at=now,
                    published_at=now,
                    price=129,
                )
            ][:max_results]

    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "search_enabled": True,
            "search_provider": CapturingProvider(),
        }
    )

    assert state["ecommerce_search_status"] == "success"
    assert any("商品销量" in query and "价格带" in query for query in queries)
    assert any("用户评价" in query and "使用场景" in query for query in queries)


def test_search_failure_falls_back_to_mock_and_records_warning():
    class FailingProvider:
        request_count = 0

        def search(self, query: str, *, max_results: int = 5):
            from src.ecommerce.search import SearchTimeoutError

            raise SearchTimeoutError("unit test timeout")

    state = run_ecommerce_graph(
        {
            "category": "便携榨汁杯",
            "search_enabled": True,
            "search_provider": FailingProvider(),
        }
    )

    assert state["ecommerce_report"]["recommendations"]
    assert state["ecommerce_search_status"] == "fallback"
    assert state["ecommerce_metrics"]["overall_status"] == "degraded"
    assert any("回退 Mock" in warning for warning in state["ecommerce_report"]["warnings"])


def test_source_filter_exhaustion_is_explicitly_diagnosed():
    class NonAllowlistedProvider:
        request_count = 0

        def search(self, query: str, *, max_results: int = 5):
            self.request_count += 1
            now = datetime.now(timezone.utc)
            return [
                SearchResult(
                    title="行业报告结果",
                    url="https://report.example/result",
                    snippet="未分级的行业摘要",
                    source="unit",
                    score=0.9,
                    retrieved_at=now,
                )
            ][:max_results]

    state = run_ecommerce_graph(
        {
            "category": "桌面收纳盒",
            "search_enabled": True,
            "search_provider": NonAllowlistedProvider(),
            "search_config": {
                "source_policy": "filter",
                "source_domain_allowlist_by_module": {"market": ["jd.com"]},
            },
        }
    )

    details = state["ecommerce_search_details"]["market"]
    assert details["status"] == "fallback"
    assert details["source_filter_exhausted"] is True
    assert details["raw_result_count"] == 1
    assert details["filtered_source_count"] == 1
    assert any("来源过滤移除了全部" in warning for warning in state["ecommerce_report"]["warnings"])


def test_search_quality_filters_are_observable():
    class QualityProvider:
        request_count = 0

        def search(self, query: str, *, max_results: int = 5):
            now = datetime.now(timezone.utc)
            return [
                SearchResult(
                    title="低分结果",
                    url="https://example.test/low",
                    snippet="低相关性",
                    source="unit",
                    score=0.2,
                    retrieved_at=now,
                ),
                SearchResult(
                    title="过期结果",
                    url="https://example.test/old",
                    snippet="过期内容",
                    source="unit",
                    score=0.9,
                    retrieved_at=now,
                    published_at=now - timedelta(days=90),
                ),
                SearchResult(
                    title="未来结果",
                    url="https://example.test/future",
                    snippet="未来内容",
                    source="unit",
                    score=0.9,
                    retrieved_at=now,
                    published_at=now + timedelta(days=3),
                ),
                SearchResult(
                    title="合格结果",
                    url="https://example.test/accepted",
                    snippet="当前内容",
                    source="unit",
                    score=0.9,
                    retrieved_at=now,
                    published_at=now,
                ),
            ][:max_results]

    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "search_enabled": True,
            "search_provider": QualityProvider(),
            "search_config": {"min_score": 0.8, "max_age_days": 30},
        }
    )

    assert state["ecommerce_search_status"] == "success"
    details = state["ecommerce_search_details"]["market"]
    assert details["filtered_low_score_count"] == 1
    assert details["filtered_stale_count"] == 1
    assert details["filtered_future_count"] == 1
    assert details["result_count"] == 1


def test_search_quality_metadata_exposes_source_price_and_freshness_limits():
    class MetadataProvider:
        request_count = 0

        def search(self, query: str, *, max_results: int = 5):
            now = datetime.now(timezone.utc)
            return [
                SearchResult(
                    title="京东商品页",
                    url="https://item.jd.com/1001.html",
                    snippet="公开商品摘要，售价 ¥129。",
                    source="unit",
                    score=0.95,
                    retrieved_at=now,
                    published_at=now,
                    price=129,
                ),
                SearchResult(
                    title="未分级来源",
                    url="https://unknown.example/result",
                    snippet="没有价格和发布时间的外部摘要。",
                    source="unit",
                    score=0.9,
                    retrieved_at=now,
                ),
            ][:max_results]

    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "search_enabled": True,
            "search_provider": MetadataProvider(),
            "search_config": {"max_age_days": 30},
        }
    )

    details = state["ecommerce_search_details"]
    assert details["market"]["source_quality_counts"]["mainland_ecommerce"] == 1
    assert details["market"]["unknown_source_count"] == 1
    assert details["market"]["freshness_status"] == "partial"
    assert details["competitor"]["explicit_price_count"] == 1
    assert details["competitor"]["placeholder_price_count"] == 1
    assert details["competitor"]["price_coverage"] == 0.5
    competitors = state["ecommerce_report"]["competitors"]
    assert [item["price_source"] for item in competitors] == ["explicit", "request_midpoint"]
    assert any("未提供发布时间" in warning for warning in state["ecommerce_report"]["warnings"])


def test_search_cache_is_opt_in_bounded_and_reapplies_quality_filtering():
    class CountingProvider:
        request_count = 0

        def search(self, query: str, *, max_results: int = 5):
            self.request_count += 1
            now = datetime.now(timezone.utc)
            return [
                SearchResult(
                    title="缓存结果",
                    url="https://item.jd.com/cached.html",
                    snippet="可重复使用的搜索摘要",
                    source="unit",
                    score=0.9,
                    retrieved_at=now,
                    published_at=now,
                )
            ]

    raw_provider = CountingProvider()
    provider = SearchBackedResearchProvider(
        raw_provider,
        cache_ttl_seconds=60,
        cache_max_entries=2,
        min_score=0.8,
        max_age_days=30,
    )
    request = EcommerceResearchRequest(category="可折叠露营桌")

    first_evidence = provider.market_research(request)[1]
    second_evidence = provider.market_research(request)[1]

    assert raw_provider.request_count == 1
    assert provider.cache_miss_count == 1
    assert provider.cache_hit_count == 1
    assert first_evidence[0].evidence_id == second_evidence[0].evidence_id
    assert provider.module_status["market"]["cache_hit"] is True
    assert provider.module_status["market"]["attempts"] == 0
    assert provider.module_status["market"]["status_code"] is None
    assert provider.module_status["market"]["freshness_status"] == "complete"


def test_parallel_search_fetches_concurrently_but_commits_modules_in_order():
    def handler(request: httpx.Request) -> httpx.Response:
        query = request.content.decode("utf-8")
        if "商品销量" in query:
            key = "market"
        elif "竞品" in query:
            key = "competitor"
        elif "用户需求" in query:
            key = "customer"
        else:
            key = "opportunity"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": f"{key}结果",
                        "url": f"https://example.test/{key}",
                        "content": f"{key}公开摘要",
                        "score": 0.9,
                    }
                ]
            },
        )

    from src.ecommerce.search import HttpJsonSearchProvider

    provider = HttpJsonSearchProvider(
        api_key="unit-test-key",
        transport=httpx.MockTransport(handler),
    )
    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "search_enabled": True,
            "search_provider": provider,
            "search_config": {"parallel_modules": True, "max_parallel_searches": 2},
        }
    )

    assert state["ecommerce_search_status"] == "success"
    assert state["ecommerce_metrics"]["external_request_count"] == 4
    assert [
        state["ecommerce_search_details"][module]["parallel_fetch"]
        for module in ("market", "competitor", "customer", "opportunity")
    ] == [True, True, True, True]


def test_parallel_search_failure_falls_back_to_serial_compensation():
    from src.ecommerce.search import SearchHTTPError, SearchResponse

    class FlakyProvider:
        request_count = 0
        parallel_safe = True

        def __init__(self):
            self.failed_queries: set[str] = set()

        def search_with_metadata(self, query: str, *, max_results: int = 5):
            self.request_count += 1
            if "竞品" in query and query not in self.failed_queries:
                self.failed_queries.add(query)
                raise SearchHTTPError(503)
            now = datetime.now(timezone.utc)
            return SearchResponse(
                results=(
                    SearchResult(
                        title="串行补偿结果",
                        url=f"https://item.jd.com/{self.request_count}.html",
                        snippet="补偿搜索摘要，售价 ¥129。",
                        source="unit",
                        score=0.9,
                        retrieved_at=now,
                        published_at=now,
                        price=129,
                    ),
                ),
                metadata={"status_code": 200, "attempts": 1},
            )

    provider = FlakyProvider()
    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "search_enabled": True,
            "search_provider": provider,
            "search_config": {"parallel_modules": True, "max_parallel_searches": 2},
        }
    )

    assert state["ecommerce_search_status"] == "success"
    assert state["ecommerce_search_details"]["competitor"]["parallel_fallback"] is True
    assert any("串行补偿" in warning for warning in state["ecommerce_report"]["warnings"])
    assert [item["supports"] for item in state["ecommerce_report"]["evidence"]] == [
        ["search:market"],
        ["search:competitor"],
        ["search:customer"],
        ["search:opportunity"],
    ]


def test_source_filter_is_opt_in_and_observable():
    class DomainProvider:
        request_count = 0

        def search(self, query: str, *, max_results: int = 5):
            self.request_count += 1
            now = datetime.now(timezone.utc)
            return [
                SearchResult(
                    title="京东结果",
                    url="https://item.jd.com/1001.html",
                    snippet="商品售价 ¥129",
                    source="unit",
                    score=0.9,
                    retrieved_at=now,
                    price=129,
                ),
                SearchResult(
                    title="外部结果",
                    url="https://unknown.example/result",
                    snippet="外部摘要",
                    source="unit",
                    score=0.95,
                    retrieved_at=now,
                ),
            ][:max_results]

    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "search_enabled": True,
            "search_provider": DomainProvider(),
            "search_config": {
                "source_domain_allowlist": ["jd.com"],
                "source_policy": "filter",
            },
        }
    )

    assert state["ecommerce_search_status"] == "success"
    assert state["ecommerce_search_details"]["market"]["filtered_source_count"] == 1
    assert state["ecommerce_search_details"]["market"]["source_policy"] == "filter"
    assert state["ecommerce_search_details"]["market"]["result_count"] == 1


def test_module_source_allowlist_only_filters_configured_module():
    class DomainProvider:
        request_count = 0
        last_request_metadata = {"result_count": 2, "returned_count": 2}

        def search(self, query: str, *, max_results: int = 5):
            self.request_count += 1
            now = datetime.now(timezone.utc)
            return [
                SearchResult(
                    title="京东结果",
                    url="https://item.jd.com/1001.html",
                    snippet="商品售价 ¥129",
                    source="unit",
                    score=0.9,
                    retrieved_at=now,
                    price=129,
                ),
                SearchResult(
                    title="外部结果",
                    url="https://unknown.example/result",
                    snippet="外部摘要",
                    source="unit",
                    score=0.95,
                    retrieved_at=now,
                ),
            ][:max_results]

    state = run_ecommerce_graph(
        {
            "category": "可折叠露营桌",
            "search_enabled": True,
            "search_provider": DomainProvider(),
            "search_config": {
                "source_domain_allowlist_by_module": {"market": ["jd.com"]},
                "source_policy": "filter",
            },
        }
    )

    details = state["ecommerce_search_details"]
    assert details["market"]["filtered_source_count"] == 1
    assert details["market"]["source_domain_allowlist"] == ["jd.com"]
    assert details["competitor"]["filtered_source_count"] == 0
    assert details["competitor"]["result_count"] == 2


def test_competitor_selection_prefers_explicit_price_even_when_result_is_third():
    class RankedProvider:
        request_count = 0

        def search(self, query: str, *, max_results: int = 5):
            now = datetime.now(timezone.utc)
            return [
                SearchResult(
                    title="无价格高分结果",
                    url="https://unknown.example/one",
                    snippet="摘要没有明确售价",
                    source="unit",
                    score=0.99,
                    retrieved_at=now,
                ),
                SearchResult(
                    title="无价格次高结果",
                    url="https://unknown.example/two",
                    snippet="摘要没有明确售价",
                    source="unit",
                    score=0.98,
                    retrieved_at=now,
                ),
                SearchResult(
                    title="有明确价格结果",
                    url="https://item.jd.com/1002.html",
                    snippet="售价 ¥129",
                    source="unit",
                    score=0.7,
                    retrieved_at=now,
                    price=129,
                ),
            ][:max_results]

    provider = SearchBackedResearchProvider(RankedProvider())
    competitors, _ = provider.competitor_research(
        EcommerceResearchRequest(category="可折叠露营桌")
    )

    assert competitors[0].price == 129.0
    assert competitors[0].price_source == "explicit"


class TestCleanCompetitorName:
    def test_strips_seo_and_site_noise(self) -> None:
        from src.ecommerce.providers import clean_competitor_name

        name, named = clean_competitor_name(
            "户外露营折叠桌 - Top 1万件户外露营折叠桌 - 2026年8月更新 - 淘宝Taobao",
            "taobao.com",
            "可折叠露营桌",
        )
        assert named is True
        assert "淘宝" not in name and "Top" not in name and "2026" not in name

    def test_extracts_brand_product_name(self) -> None:
        from src.ecommerce.providers import clean_competitor_name

        name, named = clean_competitor_name(
            "摩飞电器便携榨汁杯MR9800无线充电款",
            "taobao.com",
            "便携榨汁杯",
        )
        assert named is True
        assert "摩飞电器" in name

    def test_returns_honest_placeholder_when_unnamed(self) -> None:
        from src.ecommerce.providers import clean_competitor_name

        name, named = clean_competitor_name("图片怎么样", "x.com", "保温杯")
        assert named is False
        assert "未具名" in name
