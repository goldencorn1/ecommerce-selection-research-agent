"""Adapters that add private evidence without changing provider contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from ..models import EcommerceResearchRequest, Evidence
from ..providers import ResearchProvider
from .retriever import (
    LocalRetriever,
    RetrievalResult,
    load_knowledge_documents,
    load_knowledge_records,
    records_to_documents,
    retrieval_to_evidence,
)


class KnowledgeRetriever(Protocol):
    def search(self, query: str, *, top_k: int = 3) -> list[RetrievalResult]: ...


class KnowledgeAugmentedProvider:
    """Decorate any research provider with private candidate evidence.

    Private hits are additive: they never replace Mock/Live results, and a
    retrieval failure leaves the original provider fully usable.
    """

    def __init__(
        self,
        provider: ResearchProvider,
        retriever: KnowledgeRetriever,
        *,
        top_k: int = 3,
    ) -> None:
        self.provider = provider
        self.retriever = retriever
        self.top_k = max(1, int(top_k))
        self.knowledge_status = "not_used"
        self.knowledge_details: dict[str, Any] = {}
        self.knowledge_warnings: list[str] = []
        self._hits: list[RetrievalResult] | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.provider, name)

    def _private_evidence(
        self,
        request: EcommerceResearchRequest,
        module: str,
    ) -> list[Evidence]:
        if self._hits is None:
            query = " ".join(
                value
                for value in (
                    request.category,
                    request.target_market,
                    request.target_customer,
                )
                if value
            )
            try:
                self._hits = list(self.retriever.search(query, top_k=self.top_k))
                self.knowledge_status = "success" if self._hits else "no_hit"
                self.knowledge_details = {
                    "query": query,
                    "hit_count": len(self._hits),
                    "top_k": self.top_k,
                }
            except Exception as exc:  # noqa: BLE001 - private RAG is optional
                self._hits = []
                self.knowledge_status = "fallback"
                self.knowledge_details = {
                    "query": query,
                    "hit_count": 0,
                    "top_k": self.top_k,
                }
                warning = f"私有知识检索失败，已保留现有研究结果：{exc}"
                if warning not in self.knowledge_warnings:
                    self.knowledge_warnings.append(warning)
        return [
            retrieval_to_evidence(
                hit,
                supports=["private-knowledge", f"private:{module}"],
            )
            for hit in self._hits
        ]

    def _run(
        self,
        method: str,
        module: str,
        request: EcommerceResearchRequest,
    ) -> tuple[list[Any], list[Evidence]]:
        values, evidence = getattr(self.provider, method)(request)
        return values, list(evidence) + self._private_evidence(request, module)

    def market_research(self, request: EcommerceResearchRequest):
        return self._run("market_research", "market", request)

    def competitor_research(self, request: EcommerceResearchRequest):
        return self._run("competitor_research", "competitor", request)

    def customer_research(self, request: EcommerceResearchRequest):
        return self._run("customer_research", "customer", request)

    def opportunity_risk(self, request: EcommerceResearchRequest):
        return self._run("opportunity_risk", "risk", request)


def build_knowledge_retriever(
    config: Mapping[str, Any] | None,
) -> KnowledgeRetriever | None:
    """Build a local retriever from a serializable e-commerce config."""

    values = dict(config or {})
    retriever = values.get("retriever")
    if retriever is not None:
        return retriever
    path = values.get("path") or values.get("source_file")
    if not path:
        return None
    suffix = str(path).lower()
    if suffix.endswith((".jsonl", ".ndjson", ".csv", ".md", ".markdown", ".txt")):
        documents = records_to_documents(load_knowledge_records(path))
    else:
        documents = load_knowledge_documents(path)
    retrieval_mode = str(values.get("retrieval_mode", "keyword")).lower()
    if retrieval_mode in {"vector", "embedding", "bge"}:
        from .vector import HashEmbeddingAdapter, LexicalReranker, VectorRetriever

        reranker = LexicalReranker() if values.get("rerank", False) else None
        return VectorRetriever(
            documents,
            HashEmbeddingAdapter(dimensions=int(values.get("dimensions", 128))),
            reranker=reranker,
        )
    return LocalRetriever(documents)


__all__ = [
    "KnowledgeAugmentedProvider",
    "KnowledgeRetriever",
    "build_knowledge_retriever",
]
