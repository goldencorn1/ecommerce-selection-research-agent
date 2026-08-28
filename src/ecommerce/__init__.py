"""Standalone mock e-commerce product research MVP.

The package intentionally has no dependency on DeerFlow runtime configuration or
external services.  It can later be connected to a LangGraph node by passing the
same request and result models into an adapter.
"""

from .models import (
    CompetitorInsight,
    CustomerProfile,
    EcommerceResearchRequest,
    Evidence,
    FinalReport,
    OpportunityRisk,
    ProductScore,
    ProductRecommendation,
    TrendSignal,
)
from .orchestration import ResearchResult, run_deepseek_research, run_mock_research
from .providers import MockResearchProvider
from .observability import MemoryObservationRecorder, ObservationEvent
from .resilience import CircuitBreaker, RateLimiter

__all__ = [
    "CompetitorInsight",
    "CustomerProfile",
    "EcommerceResearchRequest",
    "Evidence",
    "FinalReport",
    "MockResearchProvider",
    "MemoryObservationRecorder",
    "ObservationEvent",
    "OpportunityRisk",
    "ProductRecommendation",
    "ProductScore",
    "ResearchResult",
    "CircuitBreaker",
    "RateLimiter",
    "TrendSignal",
    "run_deepseek_research",
    "run_mock_research",
]
