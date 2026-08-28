"""Provider-independent search adapters for the e-commerce MVP.

Adapters in this package are intentionally opt-in: importing them does not
load ``.env`` files, read API keys, or make network requests. Callers are
responsible for using data they are authorized to access and for complying
with the target service's robots rules, privacy requirements, and terms of
service.
"""

from .adapters import HttpJsonSearchProvider, TavilySearchProvider
from .cache import SearchCache, SearchCacheHit
from .errors import (
    SearchConfigurationError,
    SearchEmptyResultError,
    SearchHTTPError,
    SearchProviderError,
    SearchResponseError,
    SearchTimeoutError,
)
from .models import (
    SearchProvider,
    SearchResult,
    SearchResponse,
    SearchProviderWithMetadata,
    clean_search_results,
    normalize_search_url,
    search_result_to_evidence,
)
from .mock import MockSearchProvider
from .preflight import run_search_preflight
from .providers import (
    SUPPORTED_SEARCH_PROVIDERS,
    BraveSearchProvider,
    SearXNGSearchProvider,
    SerperSearchProvider,
    build_search_provider,
)
from .quality import SourceQuality, classify_source_domain

__all__ = [
    "HttpJsonSearchProvider",
    "MockSearchProvider",
    "SearchConfigurationError",
    "SearchCache",
    "SearchCacheHit",
    "SearchEmptyResultError",
    "SearchHTTPError",
    "SearchProvider",
    "SearchProviderError",
    "SearchResponseError",
    "SearchResult",
    "SearchResponse",
    "SearchProviderWithMetadata",
    "SearchTimeoutError",
    "SourceQuality",
    "TavilySearchProvider",
    "SUPPORTED_SEARCH_PROVIDERS",
    "BraveSearchProvider",
    "SearXNGSearchProvider",
    "SerperSearchProvider",
    "build_search_provider",
    "classify_source_domain",
    "clean_search_results",
    "normalize_search_url",
    "run_search_preflight",
    "search_result_to_evidence",
]
