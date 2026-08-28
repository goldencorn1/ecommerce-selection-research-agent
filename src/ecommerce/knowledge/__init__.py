"""Offline local-RAG and cache primitives for the e-commerce MVP."""

from .cache import CacheStats, TTLCache
from .models import KnowledgeDocument, PrivateKnowledgeRecord, RetrievalResult
from .retriever import (
    LocalRetriever,
    load_knowledge_documents,
    load_knowledge_records,
    record_to_evidence,
    records_to_documents,
    retrieval_to_evidence,
)
from .integration import KnowledgeAugmentedProvider, build_knowledge_retriever
from .vector import (
    BGEEmbeddingAdapter,
    BGERerankerAdapter,
    DeterministicEmbeddingAdapter,
    EmbeddingProvider,
    HashEmbeddingAdapter,
    LexicalReranker,
    Reranker,
    VectorRetriever,
)

__all__ = [
    "CacheStats",
    "KnowledgeDocument",
    "LocalRetriever",
    "PrivateKnowledgeRecord",
    "RetrievalResult",
    "TTLCache",
    "load_knowledge_documents",
    "load_knowledge_records",
    "record_to_evidence",
    "records_to_documents",
    "retrieval_to_evidence",
    "BGEEmbeddingAdapter",
    "BGERerankerAdapter",
    "DeterministicEmbeddingAdapter",
    "EmbeddingProvider",
    "HashEmbeddingAdapter",
    "KnowledgeAugmentedProvider",
    "LexicalReranker",
    "Reranker",
    "VectorRetriever",
    "build_knowledge_retriever",
]
