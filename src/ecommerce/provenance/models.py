"""Typed provenance records for auditable e-commerce evidence."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    title: str = Field(min_length=1)
    retrieved_at: datetime
    retrieval_score: float = Field(ge=0, le=1)
    source_type: str = Field(default="search", min_length=1)
    authorization_note: str = Field(default="来源授权状态待核验", min_length=1)

    @field_validator("source")
    @classmethod
    def valid_source_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return value
        # ``local:///absolute/path`` has an empty netloc by design; the path
        # itself is the authority for local evidence.  Keep accepting
        # ``local://workspace/id`` as well so both public URI forms remain
        # stable across the demo and API adapters.
        if parsed.scheme in {"mock", "local"} and (
            parsed.netloc or parsed.path.startswith("/")
        ):
            return value
        raise ValueError("source must be an absolute http(s), mock://, or local:// source")


class ProvenanceValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measured: str = "measured"
    complete: bool
    cited_evidence_count: int = Field(ge=0)
    mapped_source_count: int = Field(ge=0)
    missing_evidence_ids: list[str] = Field(default_factory=list)
    invalid_provenance_ids: list[str] = Field(default_factory=list)

