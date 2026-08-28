import json

import pytest

from src.ecommerce.knowledge.models import KnowledgeDocument, RetrievalResult
from src.ecommerce.knowledge.vector import (
    BGEEmbeddingAdapter,
    BGERerankerAdapter,
    DeterministicEmbeddingAdapter,
    HashEmbeddingAdapter,
    LexicalReranker,
    VectorRetriever,
)


def _docs() -> list[KnowledgeDocument]:
    return [
        KnowledgeDocument(
            document_id="b",
            title="蓝色帐篷",
            content="双人露营帐篷，防水耐风。",
            source="local://b",
        ),
        KnowledgeDocument(
            document_id="a",
            title="折叠露营桌",
            content="轻量便携，适合户外露营。",
            source="local://a",
        ),
    ]


def test_hash_embedding_is_reproducible_and_deterministic_alias_matches():
    first = HashEmbeddingAdapter(dimensions=32).embed("露营 折叠")
    second = HashEmbeddingAdapter(dimensions=32).embed("露营 折叠")
    assert first == second
    assert DeterministicEmbeddingAdapter(dimensions=32).embed("露营 折叠") == first


def test_vector_retrieval_cosine_order_and_stable_ties():
    provider = HashEmbeddingAdapter(dimensions=64)
    docs = _docs()
    retriever = VectorRetriever(docs, provider)

    results = retriever.search("露营", top_k=2)
    assert [result.document_id for result in results] == ["a", "b"]
    assert results[0].score >= results[1].score
    assert json.loads(results[0].model_dump_json())["source"] == "local://a"

    tied = VectorRetriever(
        docs, HashEmbeddingAdapter(dimensions=2), embeddings=[[1, 0], [1, 0]]
    )
    assert [result.document_id for result in tied.search("any", top_k=2)] == ["a", "b"]


def test_bge_embedding_callable_and_object_are_injected_without_optional_dependency():
    callable_adapter = BGEEmbeddingAdapter(lambda text: [len(text), 1])
    assert callable_adapter.embed("abc") == (3.0, 1.0)

    class FakeBGE:
        def encode(self, text):
            return [[float(len(text)), 2.0]]

    assert BGEEmbeddingAdapter(FakeBGE()).embed("abcd") == (4.0, 2.0)


def test_empty_corpus_query_and_non_positive_top_k():
    provider = HashEmbeddingAdapter()
    assert VectorRetriever([], provider).search("query") == []
    assert VectorRetriever(_docs(), provider).search("   ") == []
    assert VectorRetriever(_docs(), provider).search("query", top_k=0) == []


def test_lexical_reranker_reorders_candidates_and_preserves_json_contract():
    results = VectorRetriever(_docs(), HashEmbeddingAdapter()).search("露营", top_k=2)
    reranked = LexicalReranker().rerank("轻量", results)
    assert reranked[0].document_id == "a"
    assert reranked[0].score == 1.0
    assert json.loads(reranked[0].model_dump_json())["document_id"] == "a"


def test_bge_reranker_callable_and_vector_retriever_integration():
    results = VectorRetriever(_docs(), HashEmbeddingAdapter()).search("露营", top_k=2)
    reranker = BGERerankerAdapter(lambda query, texts: [0.1, 0.9])
    reranked = reranker.rerank("露营", results)
    assert [result.document_id for result in reranked] == [
        results[1].document_id,
        results[0].document_id,
    ]

    integrated = VectorRetriever(_docs(), HashEmbeddingAdapter(), reranker=reranker)
    assert integrated.search("露营", top_k=2)[0].score == pytest.approx(0.9)


def test_reranker_handles_logits_and_rejects_wrong_score_count():
    results = VectorRetriever(_docs(), HashEmbeddingAdapter()).search("露营", top_k=2)
    logits = BGERerankerAdapter(lambda pairs: [-2.0, 2.0])
    assert logits.rerank("露营", results)[0].score == pytest.approx(
        1 / (1 + 2.718281828**-2), rel=1e-5
    )

    with pytest.raises(ValueError, match="one score"):
        BGERerankerAdapter(lambda query, texts: [1.0]).rerank("露营", results)


def test_vector_dimension_mismatch_is_explicit():
    docs = _docs()
    retriever = VectorRetriever(
        docs, HashEmbeddingAdapter(), embeddings=[[1, 0], [0, 1]]
    )
    with pytest.raises(ValueError, match="same dimension"):
        retriever.search("query")


def test_protocol_compatible_result_type():
    result = VectorRetriever(_docs(), HashEmbeddingAdapter()).search("露营", top_k=1)[0]
    assert isinstance(result, RetrievalResult)
