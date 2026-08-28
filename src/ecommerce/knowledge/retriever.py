"""Keyword-overlap local retriever; intended as a no-dependency RAG seam."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .cache import TTLCache
from .models import KnowledgeDocument, PrivateKnowledgeRecord, RetrievalResult
from src.ecommerce.models import Evidence


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[\w\u4e00-\u9fff]+", text.lower()) if token}


def load_knowledge_documents(path: str | Path) -> list[KnowledgeDocument]:
    path = Path(path)
    if path.suffix.lower() == ".jsonl":
        documents = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                documents.append(KnowledgeDocument.model_validate(json.loads(line)))
        return documents
    if path.suffix.lower() in {".md", ".markdown"}:
        return [
            KnowledgeDocument(
                document_id=path.stem,
                title=path.stem,
                content=path.read_text(encoding="utf-8"),
                source=str(path),
            )
        ]
    raise ValueError("knowledge source must be .jsonl or .md")


_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "record_id": ("record_id", "document_id", "id", "记录ID", "记录编号"),
    "product": (
        "product",
        "product_name",
        "name",
        "商品",
        "商品名称",
        "产品",
        "产品名称",
    ),
    "supplier": ("supplier", "supplier_name", "供应商", "供应商名称"),
    "sku": ("sku", "SKU", "商品SKU", "SKU编码", "货号"),
    "platform": ("platform", "平台", "销售平台"),
    "price": ("price", "价格", "售价", "销售价", "商品售价"),
    "cost": ("cost", "成本", "单位成本", "采购成本", "供应商成本"),
    "sales_period": ("sales_period", "period", "销量周期", "统计周期"),
    "inventory": ("inventory", "库存", "库存数量", "可用库存"),
    "source_file": (
        "source_file",
        "source",
        "来源文件",
        "源文件",
        "文件来源",
    ),
    "updated_at": ("updated_at", "update_time", "更新时间", "更新日期"),
    "metadata": ("metadata", "元数据"),
    "title": ("title", "标题"),
    "content": ("content", "内容", "正文", "文本"),
}


def _header_key(value: Any) -> str:
    return re.sub(r"[\s_\-（）()]+", "", str(value).strip().lower())


_NORMALIZED_ALIASES = {
    _header_key(alias): canonical
    for canonical, aliases in _FIELD_ALIASES.items()
    for alias in aliases
}


def _parse_number(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("，", "")
    text = text.replace("¥", "").replace("￥", "").replace("元", "").strip()
    return float(text)


def _parse_metadata(value: Any) -> dict[str, Any]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("metadata must be a JSON object")


def _parse_inventory(value: Any) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        return parsed
    return value


def _parse_updated_at(value: Any) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _normalise_row(
    row: Mapping[Any, Any], *, source_file: str, row_number: int
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    extra_metadata: dict[str, Any] = {}
    for raw_key, value in row.items():
        if raw_key is None:
            raise ValueError("row contains extra columns")
        canonical = _NORMALIZED_ALIASES.get(_header_key(raw_key))
        if canonical is None:
            extra_metadata[str(raw_key)] = value
        else:
            normalized[canonical] = value

    normalized["record_id"] = str(
        normalized.get("record_id") or f"{Path(source_file).stem}-{row_number}"
    ).strip()
    normalized["source_file"] = str(normalized.get("source_file") or source_file)
    normalized["price"] = _parse_number(normalized.get("price"))
    normalized["cost"] = _parse_number(normalized.get("cost"))
    normalized["inventory"] = _parse_inventory(normalized.get("inventory"))
    normalized["updated_at"] = _parse_updated_at(normalized.get("updated_at"))
    normalized["metadata"] = {
        **extra_metadata,
        **_parse_metadata(normalized.get("metadata")),
    }
    for name in (
        "product",
        "supplier",
        "sku",
        "platform",
        "sales_period",
        "title",
        "content",
    ):
        if normalized.get(name) is None:
            normalized[name] = ""
        elif not isinstance(normalized[name], str):
            normalized[name] = str(normalized[name])
    return normalized


def _is_blank_row(row: Mapping[Any, Any]) -> bool:
    return not any(value is not None and str(value).strip() for value in row.values())


def _load_jsonl_records(path: Path) -> list[PrivateKnowledgeRecord]:
    records: list[PrivateKnowledgeRecord] = []
    for row_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                continue
            row = _normalise_row(payload, source_file=str(path), row_number=row_number)
            records.append(PrivateKnowledgeRecord.model_validate(row))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return records


def _load_csv_records(path: Path) -> list[PrivateKnowledgeRecord]:
    records: list[PrivateKnowledgeRecord] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), 2):
            if _is_blank_row(row):
                continue
            try:
                normalized = _normalise_row(
                    row, source_file=str(path), row_number=row_number
                )
                records.append(PrivateKnowledgeRecord.model_validate(normalized))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
    return records


def load_knowledge_records(path: str | Path) -> list[PrivateKnowledgeRecord]:
    """Load private knowledge rows from JSONL, CSV, Markdown, or plain text.

    Blank and malformed rows are ignored so one damaged upload row cannot hide
    valid private records from the same file.  The record model itself remains
    strict when used directly.
    """

    source = Path(path)
    suffix = source.suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
        return _load_jsonl_records(source)
    if suffix == ".csv":
        return _load_csv_records(source)
    if suffix in {".md", ".markdown", ".txt"}:
        content = source.read_text(encoding="utf-8-sig")
        if not content.strip():
            return []
        return [
            PrivateKnowledgeRecord(
                record_id=source.stem,
                product=source.stem,
                title=source.stem,
                content=content,
                source_file=str(source),
                metadata={"format": suffix.lstrip(".")},
            )
        ]
    raise ValueError("private knowledge source must be .jsonl, .csv, .md, or .txt")


def _local_source(source_file: str, *, fallback_id: str) -> str:
    source = source_file.strip() or fallback_id
    if source.startswith("local://"):
        return source
    return f"local://{source.replace(chr(92), '/')}"


def _record_content(record: PrivateKnowledgeRecord) -> str:
    if record.content.strip():
        return record.content
    fields = {
        "product": record.product,
        "supplier": record.supplier,
        "sku": record.sku,
        "platform": record.platform,
        "price": record.price,
        "cost": record.cost,
        "sales_period": record.sales_period,
        "inventory": record.inventory,
        "updated_at": record.updated_at,
        "metadata": record.metadata,
    }
    return json.dumps(fields, ensure_ascii=False, default=str, sort_keys=True)


def records_to_documents(
    records: Iterable[PrivateKnowledgeRecord],
) -> list[KnowledgeDocument]:
    """Adapt private records to the existing local retriever document API."""

    documents: list[KnowledgeDocument] = []
    for index, record in enumerate(records, 1):
        document_id = (
            record.record_id.strip() or record.sku.strip() or f"record-{index}"
        )
        title = record.title.strip() or record.product.strip() or document_id
        documents.append(
            KnowledgeDocument(
                document_id=document_id,
                title=title,
                content=_record_content(record),
                source=_local_source(record.source_file, fallback_id=document_id),
                source_type="local",
            )
        )
    return documents


class LocalRetriever:
    """Retrieve local documents by token overlap, with optional TTL caching."""

    def __init__(
        self,
        documents: list[KnowledgeDocument],
        *,
        cache: TTLCache[list[RetrievalResult]] | None = None,
    ):
        self.documents = documents
        self.cache = cache

    def search(self, query: str, *, top_k: int = 3) -> list[RetrievalResult]:
        if top_k <= 0:
            return []
        key = f"{query}\0{top_k}"
        if self.cache:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        query_tokens = _tokens(query)
        now = datetime.now(timezone.utc)
        scored = []
        for document in self.documents:
            doc_tokens = _tokens(f"{document.title} {document.content}")
            score = len(query_tokens & doc_tokens) / max(1, len(query_tokens))
            if score > 0:
                scored.append(
                    RetrievalResult(
                        document_id=document.document_id,
                        title=document.title,
                        content=document.content,
                        source=document.source,
                        score=round(min(1.0, score), 4),
                        retrieved_at=now,
                    )
                )
        results = sorted(scored, key=lambda item: (-item.score, item.document_id))[
            :top_k
        ]
        if self.cache:
            self.cache.set(key, results)
        return results


def retrieval_to_evidence(
    result: RetrievalResult, *, supports: list[str] | None = None
) -> Evidence:
    """Adapt a local retrieval hit to the existing evidence contract."""

    return Evidence(
        evidence_id=f"local-{result.document_id}",
        source=result.source,
        title=result.title,
        summary=result.content[:500],
        confidence=result.score,
        supports=list(supports or ["local-rag"]),
        source_type="local",
    )


def record_to_evidence(
    record: PrivateKnowledgeRecord,
    *,
    confidence: float = 0.5,
    supports: list[str] | None = None,
) -> Evidence:
    """Convert one private record to candidate-only local evidence."""

    document = records_to_documents([record])[0]
    return Evidence(
        evidence_id=f"local-{document.document_id}",
        source=document.source,
        title=document.title,
        summary=document.content[:500],
        confidence=confidence,
        supports=list(supports or ["local-rag"]),
        retrieved_at=record.updated_at,
        source_type="local",
    )
