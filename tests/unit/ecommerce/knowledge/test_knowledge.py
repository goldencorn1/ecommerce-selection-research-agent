import json
import time

from src.ecommerce.knowledge import LocalRetriever, TTLCache, load_knowledge_documents


def test_jsonl_loading_and_retrieval_order(tmp_path):
    path = tmp_path / "docs.jsonl"
    path.write_text("\n".join([
        json.dumps({"document_id":"a","title":"露营桌","content":"折叠 轻量 露营","source":"local://a"}, ensure_ascii=False),
        json.dumps({"document_id":"b","title":"收纳盒","content":"桌面 收纳","source":"local://b"}, ensure_ascii=False),
    ]), encoding="utf-8")
    docs = load_knowledge_documents(path)
    result = LocalRetriever(docs).search("露营 折叠", top_k=2)
    assert result[0].document_id == "a"
    assert result[0].score > 0


def test_cache_hit_expiry_and_capacity():
    cache = TTLCache[str](ttl_seconds=.01, max_entries=1)
    cache.set("a", "A")
    assert cache.get("a") == "A"
    cache.set("b", "B")
    assert cache.get("a") is None
    time.sleep(.02)
    assert cache.get("b") is None
    stats = cache.stats()
    assert stats.hits == 1
    assert stats.misses >= 2
    assert stats.evictions == 1
