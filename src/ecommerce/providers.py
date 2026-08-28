"""Deterministic, offline research data providers."""

from __future__ import annotations

import hashlib
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from .models import (
    CompetitorInsight,
    CustomerProfile,
    EcommerceResearchRequest,
    Evidence,
    OpportunityRisk,
    TrendSignal,
)
from .category_profiles import get_category_profile
from .search import (
    SearchCache,
    SearchProvider,
    SearchResponse,
    clean_search_results,
    search_result_to_evidence,
)
from .search.errors import SearchProviderError, SearchEmptyResultError
from .search.models import SearchResult, utc_now
from .search.quality import classify_source_domain


class ResearchProvider(Protocol):
    """Interface that a real search/data provider can implement later."""

    def market_research(self, request: EcommerceResearchRequest) -> tuple[list[TrendSignal], list[Evidence]]: ...

    def competitor_research(self, request: EcommerceResearchRequest) -> tuple[list[CompetitorInsight], list[Evidence]]: ...

    def customer_research(self, request: EcommerceResearchRequest) -> tuple[list[CustomerProfile], list[Evidence]]: ...

    def opportunity_risk(self, request: EcommerceResearchRequest) -> tuple[list[OpportunityRisk], list[Evidence]]: ...


class MockResearchProvider:
    """Generate stable research fixtures without network calls or credentials.

    ``fail_modules`` is deliberately public so tests and demos can model partial
    outages.  Values are ``market``, ``competitor``, ``customer`` and
    ``opportunity``.
    """

    DEFAULT_CATEGORY = "便携榨汁杯"

    def __init__(self, fail_modules: set[str] | None = None):
        self.fail_modules = set(fail_modules or ())

    def _seed(self, request: EcommerceResearchRequest) -> int:
        digest = hashlib.sha256(request.category.strip().encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    def _evidence(self, key: str, request: EcommerceResearchRequest, summary: str, supports: list[str]) -> Evidence:
        digest = hashlib.sha256(f"{request.category}:{key}".encode("utf-8")).hexdigest()[:10]
        labels = {
            "market": "市场趋势代理",
            "competitor": "竞品价格代理",
            "customer": "用户需求代理",
            "opportunity": "机会风险代理",
        }
        return Evidence(
            evidence_id=f"mock-{digest}",
            source="mock://ecommerce/fixtures",
            title=f"{request.category}｜{labels.get(key, key)}（Mock）",
            summary=summary,
            confidence=0.72,
            supports=supports,
        )

    def _fail_if_requested(self, module: str) -> None:
        if module in self.fail_modules:
            raise RuntimeError(f"mock provider failure: {module}")

    def market_research(self, request: EcommerceResearchRequest) -> tuple[list[TrendSignal], list[Evidence]]:
        self._fail_if_requested("market")
        seed = self._seed(request)
        demand = 62 + seed % 27
        growth = round(0.08 + (seed % 12) / 100, 2)
        profile = get_category_profile(request.category)
        evidence = self._evidence(
            "market",
            request,
            f"Mock demand proxy for {request.category} indicates interest in {profile.trend_label} and room for feature differentiation.",
            ["trend:demand", "opportunity:category"],
        )
        return [
            TrendSignal(
                name=f"{request.category}{profile.trend_label}",
                direction="rising" if demand >= 70 else "stable",
                demand_score=float(demand),
                growth_rate=growth,
                rationale=profile.trend_rationale,
                evidence_ids=[evidence.evidence_id],
            )
        ], [evidence]

    def competitor_research(self, request: EcommerceResearchRequest) -> tuple[list[CompetitorInsight], list[Evidence]]:
        self._fail_if_requested("competitor")
        seed = self._seed(request)
        price = request.price_min + (seed % 80)
        profile = get_category_profile(request.category)
        evidence = self._evidence(
            "competitor",
            request,
            f"Mock competitor scan for {request.category} shows a crowded low-end and a clearer premium niche.",
            ["competition:price", "opportunity:differentiation"],
        )
        return [
            CompetitorInsight(
                name=f"主流{request.category}品牌",
                price=round(price, 2),
                price_source="mock_fixture",
                positioning=profile.variants[0].positioning,
                strengths=["价格门槛低", "核心功能清晰"],
                weaknesses=["同质化明显", "高频体验仍需核验"],
                evidence_ids=[evidence.evidence_id],
            ),
            CompetitorInsight(
                name=f"高端{request.category}品牌",
                price=round(price * 1.8, 2),
                price_source="mock_fixture",
                positioning=profile.variants[1].positioning,
                strengths=["体验卖点更明确", "内容演示空间较大"],
                weaknesses=["价格较高", "溢价需要证据支持"],
                evidence_ids=[evidence.evidence_id],
            ),
        ], [evidence]

    def customer_research(self, request: EcommerceResearchRequest) -> tuple[list[CustomerProfile], list[Evidence]]:
        self._fail_if_requested("customer")
        profile = get_category_profile(request.category)
        evidence = self._evidence(
            "customer",
            request,
            f"Mock customer interviews for {request.category} emphasize convenience, clean-up time and trust in materials.",
            ["customer:pain_points", "customer:triggers"],
        )
        return [
            CustomerProfile(
                segment=request.target_customer,
                needs=list(profile.needs),
                pain_points=list(profile.pain_points),
                buying_triggers=list(profile.buying_triggers),
                evidence_ids=[evidence.evidence_id],
            )
        ], [evidence]

    def opportunity_risk(self, request: EcommerceResearchRequest) -> tuple[list[OpportunityRisk], list[Evidence]]:
        self._fail_if_requested("opportunity")
        seed = self._seed(request)
        opportunity = 64 + seed % 25
        risk = 28 + seed % 25
        profile = get_category_profile(request.category)
        evidence = self._evidence(
            "opportunity",
            request,
            f"Mock synthesis for {request.category}: differentiation through {profile.opportunity} is viable.",
            ["opportunity:score", "risk:quality"],
        )
        return [
            OpportunityRisk(
                opportunity=f"{request.category}{profile.opportunity}",
                rationale=profile.opportunity_rationale,
                opportunity_score=float(opportunity),
                risks=list(profile.risks),
                risk_score=float(risk),
                mitigations=list(profile.mitigations),
                evidence_ids=[evidence.evidence_id],
            )
        ], [evidence]


MAX_COMPETITORS = 4

_NAME_NOISE_SUBSTRINGS = (
    "热销", "热卖", "爆款", "新款", "排行榜", "排行", "大全", "推荐", "批发",
    "价格", "报价", "多少钱", "图片", "怎么样", "哪个牌子好", "十大品牌",
    "旗舰店", "专营", "专卖", "官网", "官方", "评价", "测评", "品牌",
)

_NAME_SITE_TOKENS = (
    "taobao", "淘宝", "天猫", "tmall", "京东", "jd", "拼多多", "苏宁",
    "suning", "amazon", "亚马逊", "1688", "alibaba", "阿里巴巴", "闲鱼",
    "抖音", "小红书", "网易", "新浪", "搜狐", "腾讯", "知乎", "百度",
    "bilibili", "哔哩", "youtube", "facebook", "instagram", "reddit",
    "joybuy", "今日头条", "什么值得买", "smzdm",
)

_NAME_SEGMENT_SPLIT = re.compile(r"[-_—–|,，、/\\【】\[\]()（）:：;；~～·•]+")
_NAME_DATE_PATTERN = re.compile(r"\d{4}\s*年(\d{1,2}\s*月)?(\d{1,2}\s*日)?(更新)?")
_NAME_COUNT_PATTERN = re.compile(r"(?i)(top\s*)?\d+(\.\d+)?\s*万[件单人]?|top\s*\d+|\d+\s*[件款单]")


def clean_competitor_name(title: str, domain: str, category: str) -> tuple[str, bool]:
    """Extract a readable competitor/product name from an SEO-heavy title.

    Returns ``(name, named)``. ``named=False`` means no usable brand/product
    token survived cleaning; the returned name is then an honest
    domain-labeled placeholder instead of a fabricated brand name.
    """

    segments = []
    for segment in _NAME_SEGMENT_SPLIT.split(title):
        candidate = segment.strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if any(token in lowered or token in candidate for token in _NAME_SITE_TOKENS):
            continue
        candidate = _NAME_DATE_PATTERN.sub("", candidate)
        candidate = _NAME_COUNT_PATTERN.sub("", candidate)
        for noise in _NAME_NOISE_SUBSTRINGS:
            candidate = candidate.replace(noise, "")
        candidate = candidate.strip(" ，。、- ")
        if len(candidate) >= 4 and candidate != category:
            segments.append(candidate)
    if not segments:
        short_domain = domain.split(":")[0][:20] if domain else "未知来源"
        return f"{short_domain}相关商品（未具名）", False
    best = max(segments, key=len)[:30]
    return best, True


class SearchBackedResearchProvider:
    """Adapt an authorized search provider to the MVP research contract.

    This provider deliberately performs lightweight deterministic synthesis from
    normalized search results. It is an integration seam, not a claim that
    snippets alone establish market truth. When search is unavailable, the
    optional Mock fallback keeps the report runnable and records a warning.
    """

    def __init__(
        self,
        search_provider: SearchProvider,
        fallback: MockResearchProvider | None = None,
        *,
        max_results: int = 5,
        min_score: float = 0.0,
        max_age_days: int | None = None,
        cache_ttl_seconds: float = 0.0,
        cache_max_entries: int = 128,
        parallel_modules: bool = False,
        max_parallel_searches: int = 4,
        parallel_fallback_to_serial: bool = True,
        source_domain_allowlist: tuple[str, ...] = (),
        source_domain_allowlist_by_module: Mapping[str, Iterable[str]] | None = None,
        source_policy: str = "annotate",
        content_enricher: Any | None = None,
    ):
        self.search_provider = search_provider
        self.fallback = fallback or MockResearchProvider()
        self.warnings: list[str] = []
        self.module_status: dict[str, dict[str, object]] = {}
        self.module_results: dict[str, list[object]] = {}
        if not 1 <= max_results <= 100:
            raise ValueError("max_results must be between 1 and 100")
        if not 0 <= min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")
        if max_age_days is not None and max_age_days < 0:
            raise ValueError("max_age_days must be non-negative")
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds must be non-negative")
        if cache_ttl_seconds > 0 and cache_max_entries < 1:
            raise ValueError("cache_max_entries must be positive when caching is enabled")
        if not 1 <= max_parallel_searches <= 4:
            raise ValueError("max_parallel_searches must be between 1 and 4")
        if source_policy not in {"annotate", "filter"}:
            raise ValueError("source_policy must be 'annotate' or 'filter'")
        self.max_results = max_results
        self.min_score = min_score
        self.max_age_days = max_age_days
        self.parallel_modules = bool(parallel_modules)
        self.max_parallel_searches = max_parallel_searches
        self.parallel_fallback_to_serial = bool(parallel_fallback_to_serial)
        self.source_domain_allowlist = tuple(
            item.strip().lower().lstrip("www.").rstrip(".")
            for item in source_domain_allowlist
            if item.strip()
        )
        self.source_domain_allowlist_by_module = {
            str(module): tuple(
                item.strip().lower().lstrip("www.").rstrip(".")
                for item in domains
                if item.strip()
            )
            for module, domains in (source_domain_allowlist_by_module or {}).items()
        }
        self.source_policy = source_policy
        self.content_enricher = content_enricher
        self._cache = (
            SearchCache(ttl_seconds=cache_ttl_seconds, max_entries=cache_max_entries)
            if cache_ttl_seconds > 0
            else None
        )
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        self._cache_counter_lock = threading.Lock()
        self._prefetched_search: dict[
            str, tuple[SearchResponse, bool, float | None] | Exception
        ] = {}
        self._parallel_fallback_modules: set[str] = set()
        self.parallel_used = False

    @property
    def request_count(self) -> int:
        return int(getattr(self.search_provider, "request_count", 0))

    @property
    def search_status(self) -> str:
        statuses = [item.get("status") for item in self.module_status.values()]
        if not statuses:
            return "not_used"
        if all(status == "success" for status in statuses):
            return "success"
        if any(status == "success" for status in statuses):
            return "partial"
        return "fallback"

    def _search(self, module: str, request: EcommerceResearchRequest) -> list[Evidence]:
        queries = self._module_queries(request)
        query = queries[module]
        prefetched = self._prefetched_search.pop(module, None)
        if isinstance(prefetched, Exception):
            raise prefetched
        if prefetched is None:
            response, cache_hit, cache_age_seconds = self._fetch_search(query)
        else:
            response, cache_hit, cache_age_seconds = prefetched
        raw_result_count = len(response.results)
        results, cleaning_details = clean_search_results(list(response.results))
        results, source_filter_details = self._filter_source_domains(module, results)
        results, quality_details = self._filter_results(results)
        enrichment_details: dict[str, Any] = {}
        if self.content_enricher is not None and module == "competitor":
            results, enrichment_details = self.content_enricher.enrich(results)
            if enrichment_details.get("data_status") == "error":
                self.warnings.append(
                    "授权商品页增强不可用，已保留 Tavily 搜索摘要；请检查数据源授权状态。"
                )
        quality_details.update(cleaning_details)
        quality_details.update(source_filter_details)
        if not results:
            raise SearchEmptyResultError(
                "Search results did not meet the configured quality threshold",
                details={"raw_result_count": raw_result_count, **quality_details},
            )
        self.module_results[module] = list(results)
        source_quality = [classify_source_domain(item.domain) for item in results]
        source_quality_counts: dict[str, int] = {}
        for item in source_quality:
            source_quality_counts[item.category] = source_quality_counts.get(item.category, 0) + 1
        mainland_relevant_count = sum(
            item.relevance.startswith("中国大陆") for item in source_quality
        )
        unknown_source_count = sum(
            item.category in {"other_domain", "unknown"} for item in source_quality
        )
        source_quality_score = round(
            sum(item.score for item in source_quality) / max(1, len(source_quality)),
            3,
        )
        quality_warnings: list[str] = []
        if unknown_source_count:
            quality_warnings.append(
                f"真实搜索{module}模块有{unknown_source_count}条来源未纳入域名分级，需人工核验相关性。"
            )
        if "中国大陆" in request.target_market and results and mainland_relevant_count == 0:
            quality_warnings.append(
                f"真实搜索{module}模块未发现可识别的中国大陆来源，结论仅作候选假设。"
            )
        undated_count = int(quality_details["undated_count"] or 0)
        if undated_count:
            freshness_message = (
                f"真实搜索{module}模块有{undated_count}条结果未提供发布时间，无法完全确认时效"
            )
            if self.max_age_days is not None:
                freshness_message += f"（max_age_days={self.max_age_days}仅对有发布时间结果生效）"
            quality_warnings.append(f"{freshness_message}。")
        self.warnings.extend(quality_warnings)
        request_metadata = dict(response.metadata)
        self.module_status[module] = {
            **request_metadata,
            "status": "success",
            "query": queries[module],
            "result_count": len(results),
            "raw_result_count": raw_result_count,
            "priced_result_count": sum(item.price is not None for item in results),
            "published_result_count": sum(item.published_at is not None for item in results),
            "unique_domain_count": len({item.domain for item in results if item.domain}),
            "source_quality_counts": source_quality_counts,
            "source_quality_score": source_quality_score,
            "mainland_relevant_count": mainland_relevant_count,
            "unknown_source_count": unknown_source_count,
            "quality_warnings": quality_warnings,
            "cache_hit": cache_hit,
            "cache_age_ms": round(cache_age_seconds * 1000, 3) if cache_age_seconds is not None else None,
            "parallel_fetch": self.parallel_used,
            "parallel_fallback": module in self._parallel_fallback_modules,
            "source_policy": self.source_policy,
            "source_domain_allowlist": list(self._source_allowlist_for_module(module)),
            "freshness_status": (
                "complete"
                if not undated_count
                else "unverified"
                if undated_count == len(results)
                else "partial"
            ),
            **enrichment_details,
            **quality_details,
        }
        return [
            search_result_to_evidence(
                result,
                supports=[f"search:{module}"],
            )
            for result in results
        ]

    @staticmethod
    def _module_queries(request: EcommerceResearchRequest) -> dict[str, str]:
        """Build module-specific queries that favor product evidence over reports."""

        return {
            "market": (
                f"{request.category} {request.target_market} 商品销量 价格带 用户需求 2025 2026"
            ),
            "competitor": f"{request.category} 竞品 价格 评价",
            "customer": f"{request.category} 用户需求 痛点 购买理由",
            "opportunity": (
                f"{request.category} {request.target_market} 用户评价 痛点 差评 使用场景 差异化"
            ),
        }

    def _source_allowlist_for_module(self, module: str) -> tuple[str, ...]:
        return self.source_domain_allowlist_by_module.get(module, self.source_domain_allowlist)

    def _filter_source_domains(
        self, module: str, results: list[SearchResult]
    ) -> tuple[list[SearchResult], dict[str, int]]:
        allowlist = self._source_allowlist_for_module(module)
        if not allowlist or self.source_policy == "annotate":
            return results, {"filtered_source_count": 0}
        accepted = [
            result
            for result in results
            if any(
                result.domain == domain or result.domain.endswith(f".{domain}")
                for domain in allowlist
            )
        ]
        return accepted, {"filtered_source_count": len(results) - len(accepted)}

    def prepare_parallel(self, request: EcommerceResearchRequest) -> bool:
        """Fetch module responses concurrently, then let orchestration commit serially.

        Only adapters that explicitly expose independent per-call responses and
        opt into ``parallel_safe`` are parallelized. Legacy providers continue
        to use the existing serial path.
        """

        self._prefetched_search.clear()
        self._parallel_fallback_modules.clear()
        self.parallel_used = False
        if not self.parallel_modules:
            return False
        search_with_metadata = getattr(self.search_provider, "search_with_metadata", None)
        if not callable(search_with_metadata) or not getattr(self.search_provider, "parallel_safe", False):
            self.warnings.append("并行搜索未启用：当前 provider 未声明线程安全，已保持串行。")
            return False
        queries = self._module_queries(request)
        with ThreadPoolExecutor(
            max_workers=min(self.max_parallel_searches, len(queries)),
            thread_name_prefix="ecommerce-search",
        ) as executor:
            futures = {
                module: executor.submit(self._fetch_search, query)
                for module, query in queries.items()
            }
            for module in queries:
                try:
                    self._prefetched_search[module] = futures[module].result()
                except Exception as exc:  # noqa: BLE001 - module fallback handles provider failures
                    if self.parallel_fallback_to_serial:
                        self._parallel_fallback_modules.add(module)
                        self.warnings.append(
                            f"并行搜索{module}模块失败，已改用串行补偿：{type(exc).__name__}。"
                        )
                    else:
                        self._prefetched_search[module] = exc
        self.parallel_used = True
        return True

    def _fetch_search(self, query: str) -> tuple[SearchResponse, bool, float | None]:
        cache_key = "|".join(
            (
                str(getattr(self.search_provider, "endpoint", "")),
                str(getattr(self.search_provider, "source", type(self.search_provider).__name__)),
                query.strip(),
                str(self.max_results),
            )
        )
        if self._cache is not None:
            cache_lookup_started = perf_counter()
            cached = self._cache.get(cache_key)
            if cached is not None:
                with self._cache_counter_lock:
                    self.cache_hit_count += 1
                metadata = dict(cached.response.metadata)
                metadata.update(
                    {
                        "cache_hit": True,
                        "cache_age_ms": round(cached.age_seconds * 1000, 3),
                        "latency_ms": round((perf_counter() - cache_lookup_started) * 1000, 3),
                        "attempts": 0,
                        "status_code": None,
                    }
                )
                return SearchResponse(results=cached.response.results, metadata=metadata), True, cached.age_seconds
            with self._cache_counter_lock:
                self.cache_miss_count += 1

        search_with_metadata = getattr(self.search_provider, "search_with_metadata", None)
        if callable(search_with_metadata):
            response = search_with_metadata(query, max_results=self.max_results)
        else:
            results = self.search_provider.search(query, max_results=self.max_results)
            response = SearchResponse(
                results=tuple(results),
                metadata=dict(getattr(self.search_provider, "last_request_metadata", None) or {}),
            )
        if self._cache is not None:
            self._cache.set(cache_key, response)
        return response, False, None

    def _filter_results(
        self, results: list[SearchResult]
    ) -> tuple[list[SearchResult], dict[str, int | float | None]]:
        """Apply conservative, observable quality filters to normalized results."""

        now = utc_now()
        accepted: list[SearchResult] = []
        low_score_count = 0
        stale_count = 0
        future_count = 0
        undated_count = 0
        for result in results:
            if result.score < self.min_score:
                low_score_count += 1
                continue
            if result.published_at is None:
                undated_count += 1
            else:
                age_seconds = (now - result.published_at).total_seconds()
                if age_seconds < -86400:
                    future_count += 1
                    continue
                if self.max_age_days is not None and age_seconds > self.max_age_days * 86400:
                    stale_count += 1
                    continue
            accepted.append(result)
        return accepted, {
            "min_score": self.min_score,
            "max_age_days": self.max_age_days,
            "filtered_low_score_count": low_score_count,
            "filtered_stale_count": stale_count,
            "filtered_future_count": future_count,
            "undated_count": undated_count,
        }

    def _with_fallback(self, module: str, request: EcommerceResearchRequest, fn):
        try:
            return fn()
        except SearchProviderError as exc:
            return self._fallback(module, request, exc.code, exc.details or {})
        except Exception as exc:  # noqa: BLE001 - keep module status truthful
            return self._fallback(
                module,
                request,
                "module_error",
                {"error_type": type(exc).__name__},
            )

    def _fallback(
        self,
        module: str,
        request: EcommerceResearchRequest,
        reason: str,
        details: dict[str, object],
    ):
        query = self._module_queries(request)[module]
        filtered_source_count = int(details.get("filtered_source_count", 0) or 0)
        raw_result_count = int(details.get("raw_result_count", 0) or 0)
        source_filter_exhausted = (
            reason == "search_empty_result"
            and raw_result_count > 0
            and filtered_source_count >= raw_result_count
        )
        self.module_status[module] = {
            "status": "fallback",
            "query": query,
            "fallback_reason": reason,
            "source_filter_exhausted": source_filter_exhausted,
            **details,
        }
        self.warnings.append(f"真实搜索{module}模块不可用，已回退 Mock：{reason}")
        if source_filter_exhausted:
            self.warnings.append(
                f"真实搜索{module}模块的来源过滤移除了全部{raw_result_count}条原始结果，"
                "当前 allowlist 可能过窄，已回退 Mock；请改用 annotate 或调整域名。"
            )
        fallback_method = f"{module}_research" if module != "opportunity" else "opportunity_risk"
        return getattr(self.fallback, fallback_method)(request)

    def market_research(self, request: EcommerceResearchRequest) -> tuple[list[TrendSignal], list[Evidence]]:
        def run():
            evidence = self._search("market", request)
            average = sum(item.confidence for item in evidence) / max(1, len(evidence))
            demand = round(55 + average * 40, 2)
            signal = TrendSignal(
                name=f"{request.category}搜索需求信号",
                direction="rising" if demand >= 70 else "stable",
                demand_score=demand,
                growth_rate=round(average * 0.12, 4),
                rationale="基于授权搜索结果摘要的初步信号，需结合平台一手数据复核。",
                evidence_ids=[item.evidence_id for item in evidence],
            )
            return [signal], evidence

        return self._with_fallback("market", request, run)

    def competitor_research(self, request: EcommerceResearchRequest) -> tuple[list[CompetitorInsight], list[Evidence]]:
        def run():
            evidence = self._search("competitor", request)
            results = self.module_results.get("competitor", [])
            midpoint = (request.price_min + request.price_max) / 2
            evidence_by_url = {
                result.canonical_url: evidence[index].evidence_id
                for index, result in enumerate(results)
                if index < len(evidence)
            }
            results = sorted(
                results,
                key=lambda result: (
                    result.price is not None,
                    classify_source_domain(result.domain).score,
                    result.score,
                ),
                reverse=True,
            )
            selected = results[:MAX_COMPETITORS]
            competitors = []
            for result in selected:
                name, named = clean_competitor_name(result.title, result.domain, request.category)
                competitors.append(
                    CompetitorInsight(
                        name=name,
                        price=round(
                            result.price if result.price is not None else midpoint,
                            2,
                        ),
                        price_source=("explicit" if result.price is not None else "request_midpoint"),
                        positioning=(
                            f"{result.domain} 搜索摘要观察，已抽取显式价格；仍需人工核验商品详情"
                            if result.price is not None
                            else f"{result.domain} 搜索摘要观察，未抽取到明确价格，暂用请求区间中点占位"
                        ),
                        strengths=(
                            ["名称来自搜索标题抽取，疑似具体商品或品牌"]
                            if named
                            else ["存在公开讨论或商品信息，但未能从标题抽取具体名称"]
                        ),
                        weaknesses=["摘要信息有限，无法替代完整商品页核验"],
                        evidence_ids=[evidence_by_url.get(result.canonical_url, "")],
                    )
                )
            named_count = sum(
                1
                for item in competitors
                if any("疑似具体商品或品牌" in strength for strength in item.strengths)
            )
            explicit_price_count = sum(result.price is not None for result in selected)
            self.module_status["competitor"].update(
                {
                    "explicit_price_count": explicit_price_count,
                    "placeholder_price_count": len(selected) - explicit_price_count,
                    "named_competitor_count": named_count,
                    "price_coverage": round(explicit_price_count / max(1, len(selected)), 2),
                    "price_anchor_values": [
                        round(result.price, 2)
                        for result in selected
                        if result.price is not None
                    ],
                    "price_anchor_min": min(
                        (result.price for result in selected if result.price is not None),
                        default=None,
                    ),
                    "price_anchor_max": max(
                        (result.price for result in selected if result.price is not None),
                        default=None,
                    ),
                }
            )
            return competitors, evidence

        return self._with_fallback("competitor", request, run)

    def customer_research(self, request: EcommerceResearchRequest) -> tuple[list[CustomerProfile], list[Evidence]]:
        def run():
            evidence = self._search("customer", request)
            profile = CustomerProfile(
                segment=request.target_customer,
                needs=["从搜索讨论中提炼高频需求"],
                pain_points=["需要人工核验摘要是否代表目标人群"],
                buying_triggers=["场景化内容和可验证的产品参数"],
                evidence_ids=[item.evidence_id for item in evidence],
            )
            return [profile], evidence

        return self._with_fallback("customer", request, run)

    def opportunity_risk(self, request: EcommerceResearchRequest) -> tuple[list[OpportunityRisk], list[Evidence]]:
        def run():
            evidence = self._search("opportunity", request)
            average = sum(item.confidence for item in evidence) / max(1, len(evidence))
            opportunity = round(55 + average * 35, 2)
            risk = round(60 - average * 30, 2)
            result = OpportunityRisk(
                opportunity=f"基于搜索信号验证{request.category}的场景化差异化方向",
                rationale="搜索结果仅支持形成候选假设，需用销量、成本和合规数据验证。",
                opportunity_score=opportunity,
                risks=["搜索摘要存在偏差", "数据时效和授权范围需要核验"],
                risk_score=risk,
                mitigations=["小批量测试", "核验原始页面和平台数据", "记录来源与抓取时间"],
                evidence_ids=[item.evidence_id for item in evidence],
            )
            return [result], evidence

        return self._with_fallback("opportunity", request, run)
