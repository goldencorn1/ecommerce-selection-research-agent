"""Authorized product-page enrichment for e-commerce search results."""

from __future__ import annotations

import html
import os
import re
from dataclasses import replace
from typing import Any, Iterable

from src.crawler.infoquest_client import InfoQuestClient

from .search.models import SearchResult


_PRICE_PATTERN = re.compile(
    r"(?:售价|价格|到手价|活动价|报价|零售价|现价|券后价)\s*(?:约|为|是|在|:|：)?\s*"
    r"(?:¥|￥|RMB\s*|人民币\s*)?([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:元|yuan|CNY)?",
    re.IGNORECASE,
)


def _plain_text(content: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", content, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def _extract_price(text: str) -> float | None:
    match = _PRICE_PATTERN.search(text)
    if not match:
        return None
    try:
        return round(float(match.group(1).replace(",", ".")), 2)
    except ValueError:
        return None


def _error_code(content: str) -> str:
    normalized = content.lower()
    if "403" in normalized or "not authorized" in normalized or "forbidden" in normalized:
        return "authorization_error"
    if "timeout" in normalized:
        return "data_timeout"
    return "data_response_error"


class InfoQuestProductEnricher:
    """Enrich a bounded number of authorized search result pages.

    InfoQuest is a page reader, not a marketplace sales API. The returned
    metadata therefore describes page-content enrichment and never claims
    verified sales, inventory, ranking, or profit data.
    """

    provider_id = "infoquest"

    def __init__(
        self,
        *,
        max_pages: int = 3,
        client: Any | None = None,
        api_key: str | None = None,
    ):
        self.max_pages = max(1, min(max_pages, 5))
        self.client = client or InfoQuestClient(
            fetch_time=5,
            timeout=20,
            navi_timeout=15,
            api_key=api_key,
        )

    @property
    def configured(self) -> bool:
        return bool(
            getattr(self.client, "api_key_set", False)
            or os.getenv("INFOQUEST_API_KEY")
        )

    def enrich(self, results: Iterable[SearchResult]) -> tuple[list[SearchResult], dict[str, Any]]:
        original = list(results)
        if not self.configured:
            return original, {
                "data_source": self.provider_id,
                "data_status": "not_configured",
                "data_requested_count": 0,
                "data_success_count": 0,
                "data_failed_count": 0,
            }

        enriched: list[SearchResult] = []
        failed_count = 0
        error_codes: set[str] = set()
        requested = original[: self.max_pages]
        for result in requested:
            content = self.client.crawl(result.url, return_format="html")
            if not isinstance(content, str) or not content.strip() or content.startswith("Error:"):
                failed_count += 1
                error_codes.add(_error_code(content if isinstance(content, str) else ""))
                enriched.append(result)
                continue
            text = _plain_text(content)
            if not text:
                failed_count += 1
                error_codes.add("empty_content")
                enriched.append(result)
                continue
            enriched.append(
                replace(
                    result,
                    snippet=text[:1200],
                    price=result.price if result.price is not None else _extract_price(text),
                    source=f"{result.source}+{self.provider_id}",
                )
            )
        enriched.extend(original[self.max_pages :])
        success_count = len(requested) - failed_count
        return enriched, {
            "data_source": self.provider_id,
            "data_status": "success" if success_count else "error",
            "data_requested_count": len(requested),
            "data_success_count": success_count,
            "data_failed_count": failed_count,
            "data_error_code": next(iter(error_codes), None),
            "data_claim_boundary": "页面内容增强，不代表销量、库存、榜单或利润已验证",
        }


def run_infoquest_preflight(
    url: str = "https://www.example.com",
    *,
    timeout: int = 20,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Check the configured InfoQuest page-reader API without exposing secrets."""

    import time

    started = time.perf_counter()
    configured = bool(api_key or os.getenv("INFOQUEST_API_KEY"))
    if not configured:
        return {
            "status": "error",
            "provider": "infoquest",
            "configured": False,
            "reachable": False,
            "error_code": "config_error",
            "message": "需要配置 INFOQUEST_API_KEY。",
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    try:
        content = InfoQuestClient(
            fetch_time=5,
            timeout=timeout,
            navi_timeout=timeout,
            api_key=api_key,
        ).crawl(url, return_format="html")
        if not isinstance(content, str) or not content.strip() or content.startswith("Error:"):
            return {
                "status": "error",
                "provider": "infoquest",
                "configured": True,
                "reachable": False,
                "error_code": _error_code(content if isinstance(content, str) else ""),
                "message": (
                    "InfoQuest API Key 未被授权调用当前服务。"
                    if isinstance(content, str) and _error_code(content) == "authorization_error"
                    else "InfoQuest 已返回，但没有获得可用页面内容。"
                ),
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        return {
            "status": "success",
            "provider": "infoquest",
            "configured": True,
            "reachable": True,
            "error_code": None,
            "content_chars": len(content),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    except Exception:  # noqa: BLE001 - keep external diagnostics secret-safe
        return {
            "status": "error",
            "provider": "infoquest",
            "configured": True,
            "reachable": False,
            "error_code": "data_request_error",
            "message": "InfoQuest 预检失败，请检查配置、网络或服务额度。",
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
