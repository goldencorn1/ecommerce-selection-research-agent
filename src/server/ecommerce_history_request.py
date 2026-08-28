from __future__ import annotations

from pydantic import BaseModel, Field


class EcommerceCompareRequest(BaseModel):
    report_ids: list[str] = Field(min_length=1, max_length=10)
