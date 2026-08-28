"""Request models for the interactive e-commerce demo workspace."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class EcommerceBYOKConfig(BaseModel):
    """Temporary request-scoped credentials; never persisted by the server."""

    model_api_key: SecretStr | None = Field(default=None, max_length=500)
    model_base_url: str | None = Field(default=None, max_length=500)
    model_name: str | None = Field(default=None, max_length=120)
    search_api_key: SecretStr | None = Field(default=None, max_length=500)
    data_api_key: SecretStr | None = Field(default=None, max_length=500)


class EcommerceWebResearchRequest(BaseModel):
    category: str = Field(default="可折叠露营桌", min_length=1, max_length=80)
    market: str = Field(default="中国大陆电商", min_length=1, max_length=80)
    customer: str | None = Field(default=None, max_length=120)
    price_min: float = Field(default=99.0, ge=0)
    price_max: float = Field(default=299.0, ge=0)
    top_n: int = Field(default=3, ge=1, le=10)
    mode: Literal["mock", "live"] = "mock"
    model: Literal["mock", "deepseek", "openai_compatible", "ollama"] = "mock"
    data_source: Literal["none", "infoquest"] = "none"
    search_provider: Literal["tavily", "searxng", "brave", "serper", "custom_http_json"] | None = None
    search_endpoint: str | None = Field(default=None, max_length=500)
    byok: EcommerceBYOKConfig | None = None
    knowledge_file_id: str | None = Field(default=None, max_length=120)
    search_parallel: bool = False
    search_timeout: float = Field(default=20.0, gt=0, le=120)
    search_retries: int = Field(default=1, ge=0, le=3)


class EcommercePreflightRequest(BaseModel):
    """Request for secret-safe search/model connectivity checks."""

    provider: Literal["all", "search", "model", "data"] = "all"
    model: Literal["mock", "deepseek", "openai_compatible", "ollama"] = "deepseek"
    # ``none`` is the default web selection and must remain valid for a
    # model-only or search-only preflight.  Previously the preflight schema
    # accepted only InfoQuest, so the normal frontend payload was rejected
    # with HTTP 422 before any check could run.
    data_source: Literal["none", "infoquest"] = "none"
    search_provider: Literal["tavily", "searxng", "brave", "serper", "custom_http_json"] | None = None
    search_endpoint: str | None = Field(default=None, max_length=500)
    byok: EcommerceBYOKConfig | None = None
    query: str = Field(default="可折叠露营桌 中国大陆电商 竞品 价格 用户需求", min_length=1, max_length=160)
    url: str = Field(default="https://www.example.com", min_length=8, max_length=500)
    timeout: float = Field(default=20.0, gt=0, le=30)
    max_results: int = Field(default=3, ge=1, le=10)


class AuthorizedDataSourceRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=1, max_length=120)
    source_kind: Literal["marketplace_api", "reader", "owned_file", "internal_db"]
    authorization_status: Literal["verified", "user_declared", "blocked"]
    authorization_reference: str = Field(min_length=1, max_length=500)
    terms_url: str | None = Field(default=None, max_length=500)
    allowed_use: str = Field(min_length=1, max_length=500)
    owner_id: str = Field(min_length=1, max_length=80)


class AuthorizedDataValidationRequest(BaseModel):
    source: AuthorizedDataSourceRequest
    records: list[dict[str, object]] = Field(min_length=1, max_length=5000)
    max_age_hours: int = Field(default=72, ge=1, le=24 * 365)


class ProductApiFieldMapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="title", min_length=1, max_length=120)
    price: str = Field(default="price", min_length=1, max_length=120)
    url: str = Field(default="url", min_length=1, max_length=120)
    sku: str = Field(default="sku", min_length=1, max_length=120)


class ProductApiConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(default="user-product-api", min_length=1, max_length=120)
    provider: str = Field(default="用户商品 API", min_length=1, max_length=120)
    endpoint: str = Field(min_length=8, max_length=500)
    method: Literal["GET", "POST"] = "GET"
    auth_mode: Literal["bearer", "header", "none"] = "bearer"
    api_key: SecretStr | None = Field(default=None, max_length=500)
    auth_header_name: str = Field(default="Authorization", min_length=1, max_length=80)
    query_param: str = Field(default="q", min_length=1, max_length=50)
    category: str = Field(default="可折叠露营桌", min_length=1, max_length=120)
    response_path: str = Field(default="data", max_length=120)
    field_map: ProductApiFieldMapRequest = Field(default_factory=ProductApiFieldMapRequest)
    max_results: int = Field(default=10, ge=1, le=50)
    timeout: float = Field(default=15.0, gt=0, le=30)
    authorization_status: Literal["verified", "user_declared", "blocked"] = "user_declared"
    authorization_reference: str = Field(default="user-declared", min_length=1, max_length=500)
    terms_url: str | None = Field(default=None, max_length=500)
    allowed_use: str = Field(default="用户声明已获授权的商品数据读取", min_length=1, max_length=500)


class ProductApiPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: ProductApiConfigRequest
