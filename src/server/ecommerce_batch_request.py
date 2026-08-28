"""Batch research request models for the e-commerce workspace."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .ecommerce_request import EcommerceBYOKConfig


class EcommerceBatchItem(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    market: str = Field(default="中国大陆电商", min_length=1, max_length=80)
    customer: str | None = Field(default=None, max_length=120)
    price_min: float = Field(default=99.0, ge=0)
    price_max: float = Field(default=299.0, ge=0)
    top_n: int = Field(default=3, ge=1, le=10)

    def model_post_init(self, __context: object) -> None:
        if self.price_max < self.price_min:
            raise ValueError("price_max must be greater than or equal to price_min")


class EcommerceBatchResearchRequest(BaseModel):
    items: list[EcommerceBatchItem] = Field(min_length=1, max_length=10)
    mode: Literal["mock", "live"] = "mock"
    model: Literal["mock", "deepseek", "openai_compatible", "ollama"] = "mock"
    data_source: Literal["none", "infoquest"] = "none"
    search_provider: Literal["tavily", "searxng", "brave", "serper", "custom_http_json"] | None = None
    search_endpoint: str | None = Field(default=None, max_length=500)
    byok: EcommerceBYOKConfig | None = None
    search_parallel: bool = False
    search_timeout: float = Field(default=20.0, gt=0, le=120)
    search_retries: int = Field(default=1, ge=0, le=3)
    max_concurrency: int = Field(default=2, ge=1, le=4)
