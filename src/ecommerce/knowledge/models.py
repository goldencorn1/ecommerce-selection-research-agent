"""Models for a deliberately lightweight local knowledge base."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_type: str = "local"


class PrivateKnowledgeRecord(BaseModel):
    """A JSON-safe row from a user's private commerce knowledge base.

    The fields intentionally describe observations and their provenance.  A
    record can therefore be retrieved as evidence without being treated as a
    verified commercial decision.
    """

    model_config = ConfigDict(extra="forbid")

    record_id: str = ""
    product: str = ""
    supplier: str = ""
    sku: str = ""
    platform: str = ""
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    sales_period: str = ""
    inventory: int | float | str | list[Any] | dict[str, Any] | None = None
    source_file: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    title: str = ""
    content: str = ""

    @classmethod
    def _json_safe_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must contain only JSON-safe values") from exc
        return value

    _validate_metadata = field_validator("metadata")(_json_safe_metadata)

    @field_validator("inventory", mode="before")
    @classmethod
    def normalise_inventory(cls, value: Any) -> Any:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                number = float(text.replace(",", "").replace("，", ""))
            except ValueError:
                return value
            return int(number) if number.is_integer() else number
        if isinstance(value, bool):
            raise ValueError("inventory must be a non-negative number or text")
        if isinstance(value, (int, float)) and (
            value < 0 or (isinstance(value, float) and not math.isfinite(value))
        ):
            raise ValueError("inventory must be non-negative")
        return value

    @field_validator("updated_at")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        return value


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    content: str
    source: str
    score: float = Field(ge=0, le=1)
    retrieved_at: datetime
