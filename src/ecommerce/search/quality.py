"""Conservative source-quality annotations for search evidence.

These annotations are observability metadata, not a claim that a domain is
factually authoritative.  Results remain available to the workflow; callers
can decide whether a source policy should filter them later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceQuality:
    """Small, explainable source classification used in search telemetry."""

    category: str
    relevance: str
    score: float


_MAINLAND_ECOMMERCE = (
    "jd.com",
    "taobao.com",
    "tmall.com",
    "1688.com",
    "pinduoduo.com",
    "yangkeduo.com",
    "douyin.com",
    "kuaishou.com",
)
_MAINLAND_CONTENT = (
    "zhihu.com",
    "xiaohongshu.com",
    "weibo.com",
    "bilibili.com",
    "baidu.com",
)
_INDUSTRY_MEDIA = (
    "36kr.com",
    "sohu.com",
    "sina.com.cn",
    "qq.com",
    "163.com",
    "ifeng.com",
)
_INTERNATIONAL_ECOMMERCE = (
    "amazon.com", "amazon.cn", "ebay.com", "ebay.cn", "aliexpress.com",
    "walmart.com", "etsy.com",
)
_OFFICIAL_BRAND = (
    "apple.com", "nike.com", "adidas.com", "xiaomi.com", "mi.com",
)


def _matches(domain: str, roots: tuple[str, ...]) -> bool:
    return any(domain == root or domain.endswith(f".{root}") for root in roots)


def classify_source_domain(domain: str) -> SourceQuality:
    """Classify a normalized domain without rejecting or fetching it."""

    normalized = domain.strip().lower().rstrip(".")
    if _matches(normalized, _MAINLAND_ECOMMERCE):
        return SourceQuality("mainland_ecommerce", "中国大陆电商相关", 1.0)
    if _matches(normalized, _MAINLAND_CONTENT):
        return SourceQuality("mainland_content", "中国大陆内容相关", 0.8)
    if _matches(normalized, _INDUSTRY_MEDIA):
        return SourceQuality("industry_media", "行业/媒体参考", 0.7)
    if _matches(normalized, _INTERNATIONAL_ECOMMERCE):
        return SourceQuality("international_ecommerce", "国际电商参考", 0.75)
    if _matches(normalized, _OFFICIAL_BRAND):
        return SourceQuality("official_brand", "品牌官方来源", 0.9)
    if normalized:
        return SourceQuality("other_domain", "未纳入本地规则的外部来源", 0.4)
    return SourceQuality("unknown", "无法识别域名", 0.0)
