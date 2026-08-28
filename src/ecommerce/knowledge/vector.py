"""Offline vector retrieval and reranking adapters for the local knowledge base.

The adapters in this module deliberately depend on no model-serving package.  A
real BGE model can be supplied by the application, while the hash adapter makes
the retrieval seam useful in tests and offline development.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol

from .models import KnowledgeDocument, RetrievalResult


Vector = Sequence[float]


class EmbeddingProvider(Protocol):
    """Provider capable of turning one piece of text into a numeric vector."""

    def embed(self, text: str) -> Vector:
        """Return an embedding for ``text``."""


def _tokens(text: str) -> list[str]:
    tokens = []
    for token in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text.lower()):
        tokens.append(token)
        if all("\u4e00" <= char <= "\u9fff" for char in token):
            tokens.extend(token)
            tokens.extend(token[index : index + 2] for index in range(len(token) - 1))
    return tokens


def _as_vector(value: Any) -> tuple[float, ...]:
    """Convert common Python and array-library vector results to a tuple."""

    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if value and isinstance(value[0], Sequence):
            value = value[0]
        vector = tuple(float(item) for item in value)
    else:
        raise TypeError("embedding backend must return a one-dimensional sequence")
    if not vector:
        raise ValueError("embedding vectors must not be empty")
    if not all(math.isfinite(item) for item in vector):
        raise ValueError("embedding vectors must contain only finite numbers")
    return vector


def _normalise(vector: Vector) -> tuple[float, ...]:
    values = tuple(float(item) for item in vector)
    norm = math.sqrt(sum(item * item for item in values))
    if norm == 0:
        return values
    return tuple(item / norm for item in values)


class HashEmbeddingAdapter:
    """A deterministic, token-hashed embedding provider with no network calls.

    Feature hashing gives identical tokens identical directions, so documents
    sharing terms with a query receive useful cosine scores while remaining
    completely reproducible across Python processes.
    """

    def __init__(
        self,
        dimensions: int = 128,
        *,
        dimension: int | None = None,
        dim: int | None = None,
        normalize: bool = True,
    ) -> None:
        if dimension is not None:
            dimensions = dimension
        if dim is not None:
            dimensions = dim
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions
        self.normalize = normalize

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[bucket] += sign
        return _normalise(vector) if self.normalize else tuple(vector)

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self.embed(text)

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self.embed(text) for text in texts]


class DeterministicEmbeddingAdapter(HashEmbeddingAdapter):
    """Descriptive alias for :class:`HashEmbeddingAdapter`."""


class BGEEmbeddingAdapter:
    """Adapt an injected BGE-compatible callable or object.

    Supported object methods are ``embed_query``, ``embed``, and ``encode``.
    ``encode`` may return either one vector or a one-row batch, which covers
    common BGE and SentenceTransformer-style wrappers without importing either
    package.
    """

    def __init__(
        self,
        backend: Any = None,
        *,
        embedder: Any = None,
        normalize: bool = False,
    ) -> None:
        if backend is not None and embedder is not None:
            raise ValueError("provide backend or embedder, not both")
        self.backend = backend if backend is not None else embedder
        if self.backend is None:
            raise ValueError("a callable or BGE-compatible backend is required")
        self.normalize = normalize

    def embed(self, text: str) -> tuple[float, ...]:
        backend = self.backend
        value: Any
        for method_name in ("embed_query", "embed", "encode"):
            method = getattr(backend, method_name, None)
            if callable(method):
                value = method(text)
                vector = _as_vector(value)
                return _normalise(vector) if self.normalize else vector
        if not callable(backend):
            raise TypeError("BGE backend must be callable or expose embed/encode")
        vector = _as_vector(backend(text))
        return _normalise(vector) if self.normalize else vector

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self.embed(text)

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self.embed(text) for text in texts]


class Reranker(Protocol):
    """Rerank vector-retrieval candidates for a query."""

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        *,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """Return candidates ordered by the reranking score."""


def _with_score(result: RetrievalResult, score: float) -> RetrievalResult:
    return result.model_copy(update={"score": max(0.0, min(1.0, score))})


class LexicalReranker:
    """Small offline reranker based on query-term coverage."""

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        *,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip() or not results:
            return []
        query_tokens = set(_tokens(query))
        if not query_tokens:
            return []
        scored = []
        for index, result in enumerate(results):
            document_tokens = set(_tokens(f"{result.title} {result.content}"))
            score = len(query_tokens & document_tokens) / len(query_tokens)
            scored.append((score, index, _with_score(result, score)))
        ordered = sorted(scored, key=lambda item: (-item[0], item[1]))
        if top_k is not None and top_k <= 0:
            return []
        return [item[2] for item in ordered[:top_k]]


def _backend_scores(value: Any) -> list[float]:
    if isinstance(value, Mapping):
        for key in ("scores", "score", "logits"):
            if key in value:
                value = value[key]
                break
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if value and isinstance(value[0], Mapping):
            value = [item.get("score", item.get("logit")) for item in value]
        if value and isinstance(value[0], Sequence):
            value = [item[0] for item in value]
        return [float(item) for item in value]
    return [float(value)]


def _score_to_unit_interval(scores: Sequence[float]) -> list[float]:
    if all(0.0 <= score <= 1.0 for score in scores):
        return list(scores)
    return [1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, score)))) for score in scores]


class BGERerankerAdapter:
    """Adapt an injected BGE reranker callable or common model wrapper."""

    def __init__(self, backend: Any = None, *, reranker: Any = None) -> None:
        if backend is not None and reranker is not None:
            raise ValueError("provide backend or reranker, not both")
        self.backend = backend if backend is not None else reranker
        if self.backend is None:
            raise ValueError("a callable or BGE-compatible reranker is required")

    def _scores(self, query: str, results: Sequence[RetrievalResult]) -> list[float]:
        texts = [f"{result.title} {result.content}" for result in results]
        pairs = [(query, text) for text in texts]
        backend = self.backend
        if callable(getattr(backend, "compute_score", None)):
            value = backend.compute_score(pairs)
        elif callable(getattr(backend, "predict", None)):
            value = backend.predict(pairs)
        elif callable(getattr(backend, "rerank", None)):
            value = backend.rerank(query, texts)
        elif callable(backend):
            try:
                value = backend(query, texts)
            except TypeError:
                value = backend(pairs)
        else:
            raise TypeError(
                "BGE reranker must be callable or expose predict/compute_score"
            )
        scores = _backend_scores(value)
        if len(scores) != len(results):
            raise ValueError("reranker must return one score per result")
        return _score_to_unit_interval(scores)

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        *,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip() or not results:
            return []
        if top_k is not None and top_k <= 0:
            return []
        scores = self._scores(query, results)
        ordered = sorted(
            zip(scores, results, strict=True),
            key=lambda item: -item[0],
        )
        reranked = [_with_score(result, score) for score, result in ordered]
        return reranked[:top_k]


def _embed(provider: EmbeddingProvider, text: str) -> tuple[float, ...]:
    method = getattr(provider, "embed", None)
    if callable(method):
        return _as_vector(method(text))
    query_method = getattr(provider, "embed_query", None)
    if callable(query_method):
        return _as_vector(query_method(text))
    if callable(provider):
        return _as_vector(provider(text))
    raise TypeError("embedding provider must expose embed or embed_query")


def _cosine(left: Vector, right: Vector) -> float:
    if len(left) != len(right):
        raise ValueError("all embedding vectors must have the same dimension")
    left_norm = math.sqrt(sum(item * item for item in left))
    right_norm = math.sqrt(sum(item * item for item in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


class VectorRetriever:
    """In-memory cosine retriever over :class:`KnowledgeDocument` objects."""

    def __init__(
        self,
        documents: Sequence[KnowledgeDocument],
        embedding_provider: EmbeddingProvider,
        *,
        embeddings: Mapping[str, Vector] | Sequence[Vector] | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.documents = list(documents)
        self.embedding_provider = embedding_provider
        self.reranker = reranker
        self._document_embeddings = self._load_embeddings(embeddings)

    def _load_embeddings(
        self,
        embeddings: Mapping[str, Vector] | Sequence[Vector] | None,
    ) -> list[tuple[float, ...]]:
        if embeddings is None:
            return [
                _embed(self.embedding_provider, f"{document.title}\n{document.content}")
                for document in self.documents
            ]
        if isinstance(embeddings, Mapping):
            return [
                _as_vector(embeddings[document.document_id])
                for document in self.documents
            ]
        if len(embeddings) != len(self.documents):
            raise ValueError("embeddings must contain one vector per document")
        return [_as_vector(vector) for vector in embeddings]

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
        reranker: Reranker | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip() or top_k <= 0 or not self.documents:
            return []
        query_vector = _embed(self.embedding_provider, query)
        now = datetime.now(timezone.utc)
        scored = []
        for index, (document, embedding) in enumerate(
            zip(self.documents, self._document_embeddings, strict=True)
        ):
            score = max(0.0, min(1.0, _cosine(query_vector, embedding)))
            scored.append(
                (
                    score,
                    document.document_id,
                    index,
                    RetrievalResult(
                        document_id=document.document_id,
                        title=document.title,
                        content=document.content,
                        source=document.source,
                        score=score,
                        retrieved_at=now,
                    ),
                )
            )
        results = [
            item[3]
            for item in sorted(scored, key=lambda item: (-item[0], item[1], item[2]))[
                :top_k
            ]
        ]
        selected_reranker = reranker if reranker is not None else self.reranker
        if selected_reranker is not None:
            return selected_reranker.rerank(query, results, top_k=top_k)
        return results

    retrieve = search


__all__ = [
    "BGEEmbeddingAdapter",
    "BGERerankerAdapter",
    "DeterministicEmbeddingAdapter",
    "EmbeddingProvider",
    "HashEmbeddingAdapter",
    "LexicalReranker",
    "Reranker",
    "VectorRetriever",
]
