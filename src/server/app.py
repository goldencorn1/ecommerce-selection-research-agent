# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import asyncio
import base64
import json
import logging
import os
import re
import tempfile
from time import perf_counter
from statistics import mean
from pathlib import Path
from typing import Annotated, Any, List, Optional, cast
from uuid import uuid4

# Load environment variables from .env file FIRST
# This must happen before checking DEBUG environment variable
from dotenv import load_dotenv
load_dotenv()

# Configure logging based on DEBUG environment variable
# This must happen early, before other modules are imported
_debug_mode = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
if _debug_mode:
    logging.getLogger("src").setLevel(logging.DEBUG)
    logging.getLogger("langchain").setLevel(logging.DEBUG)
    logging.getLogger("langgraph").setLevel(logging.DEBUG)

from fastapi import FastAPI, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from langchain_core.messages import AIMessageChunk, BaseMessage, ToolMessage
from langgraph.checkpoint.mongodb import AsyncMongoDBSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.config.configuration import get_recursion_limit
from src.config.loader import get_bool_env, get_int_env, get_str_env
from src.config.report_style import ReportStyle
from src.config.tools import SELECTED_RAG_PROVIDER
from src.citations import merge_citations
from src.graph.builder import build_graph_with_memory
from src.graph.checkpoint import chat_stream_message
from src.graph.utils import (
    build_clarified_topic_from_history,
    reconstruct_clarification_history,
)
from src.llms.llm import get_configured_llm_models
from src.podcast.graph.builder import build_graph as build_podcast_graph
from src.ppt.graph.builder import build_graph as build_ppt_graph
from src.prompt_enhancer.graph.builder import build_graph as build_prompt_enhancer_graph
from src.prose.graph.builder import build_graph as build_prose_graph
from src.eval import ReportEvaluator
from src.ecommerce.provenance import (
    build_candidate_catalog,
    import_verification_rows,
    preview_import_file,
)
from src.ecommerce.report_export import render_html_report
from src.ecommerce.capabilities import build_ecommerce_capabilities
from src.ecommerce.authorized_data import (
    AuthorizedDataSource,
    AuthorizedProductRecord,
    validate_authorized_dataset,
)
from src.ecommerce.authorized_adapters import list_authorized_adapters
from src.ecommerce.product_api import ProductApiConfig, probe_product_api
from src.ecommerce.model_preflight import run_model_preflight
from src.ecommerce.byok import runtime_credentials
from src.ecommerce.batch import EcommerceBatchTaskManager
from src.ecommerce.product_data import run_infoquest_preflight
from src.ecommerce.observability import MemoryObservationRecorder, ObservationEvent
from src.ecommerce.quality_audit import audit_report_payload
from src.ecommerce.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    RateLimitExceeded,
    RateLimiter,
    classify_failure,
)
from src.ecommerce_graph import run_ecommerce_graph
from src.rag.builder import build_retriever
from src.rag.milvus import load_examples as load_milvus_examples
from src.rag.qdrant import load_examples as load_qdrant_examples
from src.rag.retriever import Resource
from src.server.chat_request import (
    ChatRequest,
    EnhancePromptRequest,
    GeneratePodcastRequest,
    GeneratePPTRequest,
    GenerateProseRequest,
    TTSRequest,
)
from src.server.eval_request import EvaluateReportRequest, EvaluateReportResponse
from src.server.ecommerce_request import EcommerceWebResearchRequest
from src.server.ecommerce_request import (
    AuthorizedDataValidationRequest,
    EcommercePreflightRequest,
    ProductApiPreflightRequest,
)
from src.server.workspace_security import (
    issue_workspace_token,
    verify_workspace_token,
    workspace_auth_mode,
    workspace_token_required,
    workspace_token_secret,
)
from src.server.tenant_auth import (
    bearer_auth_required,
    decode_bearer_token,
)
from src.server.oidc_auth import decode_oidc_bearer_token, oidc_provider_enabled
from src.server.ecommerce_batch_request import EcommerceBatchResearchRequest
from src.server.ecommerce_history_request import EcommerceCompareRequest
from src.server.ecommerce_ui import ECOMMERCE_FALLBACK_HTML
from src.server.ecommerce_store import EcommerceReportStore
from src.server.config_request import ConfigResponse
from src.server.mcp_request import MCPServerMetadataRequest, MCPServerMetadataResponse
from src.server.mcp_utils import load_mcp_tools
from src.server.rag_request import (
    RAGConfigResponse,
    RAGResourceRequest,
    RAGResourcesResponse,
)
from src.tools import VolcengineTTS
from src.utils.json_utils import sanitize_args
from src.utils.log_sanitizer import (
    sanitize_agent_name,
    sanitize_log_input,
    sanitize_thread_id,
    sanitize_tool_name,
    sanitize_user_content,
)

logger = logging.getLogger(__name__)

# Configure Windows event loop policy for PostgreSQL compatibility
# On Windows, psycopg requires a selector-based event loop, not the default ProactorEventLoop
if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

INTERNAL_SERVER_ERROR_DETAIL = "Internal Server Error"

# Global connection pools (initialized at startup if configured)
_pg_pool: Optional[AsyncConnectionPool] = None
_pg_checkpointer: Optional[AsyncPostgresSaver] = None

# Global MongoDB connection (initialized at startup if configured)
_mongo_client: Optional[Any] = None
_mongo_checkpointer: Optional[AsyncMongoDBSaver] = None


def _runtime_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _runtime_float(name: str, default: float) -> float:
    try:
        return max(0.001, float(os.getenv(name, str(default))))
    except ValueError:
        return default


_ecommerce_rate_limiter = RateLimiter(
    limit=_runtime_int("ECOMMERCE_RATE_LIMIT_PER_WINDOW", 60),
    window_seconds=_runtime_float("ECOMMERCE_RATE_LIMIT_WINDOW_SECONDS", 60.0),
)
_ecommerce_circuit_breaker = CircuitBreaker(
    failure_threshold=_runtime_int("ECOMMERCE_CIRCUIT_FAILURE_THRESHOLD", 3),
    recovery_timeout=_runtime_float("ECOMMERCE_CIRCUIT_RECOVERY_SECONDS", 30.0),
    name="ecommerce-research",
)
_ecommerce_observations = MemoryObservationRecorder(
    max_events=_runtime_int("ECOMMERCE_OBSERVABILITY_BUFFER_SIZE", 500)
)


from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    """
    Application lifecycle manager
    - Startup: Register asyncio exception handler and initialize global connection pools
    - Shutdown: Clean up global connection pools
    """
    global _pg_pool, _pg_checkpointer, _mongo_client, _mongo_checkpointer

    # ========== STARTUP ==========
    try:
        asyncio.get_running_loop()

    except RuntimeError as e:
        logger.warning(f"Could not register asyncio exception handler: {e}")

    # Initialize global connection pool based on configuration
    checkpoint_saver = get_bool_env("LANGGRAPH_CHECKPOINT_SAVER", False)
    checkpoint_url = get_str_env("LANGGRAPH_CHECKPOINT_DB_URL", "")

    if not checkpoint_saver or not checkpoint_url:
        logger.info("Checkpoint saver not configured, skipping connection pool initialization")
    else:
        # Initialize PostgreSQL connection pool
        if checkpoint_url.startswith("postgresql://"):
            pool_min_size = get_int_env("PG_POOL_MIN_SIZE", 5)
            pool_max_size = get_int_env("PG_POOL_MAX_SIZE", 20)
            pool_timeout = get_int_env("PG_POOL_TIMEOUT", 60)

            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            }

            logger.info(
                f"Initializing global PostgreSQL connection pool: "
                f"min_size={pool_min_size}, max_size={pool_max_size}, timeout={pool_timeout}s"
            )

            try:
                _pg_pool = AsyncConnectionPool(
                    checkpoint_url,
                    kwargs=connection_kwargs,
                    min_size=pool_min_size,
                    max_size=pool_max_size,
                    timeout=pool_timeout,
                )
                await _pg_pool.open()

                _pg_checkpointer = AsyncPostgresSaver(_pg_pool)
                await _pg_checkpointer.setup()

                logger.info("Global PostgreSQL connection pool initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
                _pg_pool = None
                _pg_checkpointer = None
                raise RuntimeError(
                    "Checkpoint persistence is explicitly configured with PostgreSQL, "
                    "but initialization failed. Application will not start."
                ) from e

        # Initialize MongoDB connection pool
        elif checkpoint_url.startswith("mongodb://"):
            try:
                from motor.motor_asyncio import AsyncIOMotorClient

                # MongoDB connection pool settings
                mongo_max_pool_size = get_int_env("MONGO_MAX_POOL_SIZE", 20)
                mongo_min_pool_size = get_int_env("MONGO_MIN_POOL_SIZE", 5)

                logger.info(
                    f"Initializing global MongoDB connection pool: "
                    f"min_pool_size={mongo_min_pool_size}, max_pool_size={mongo_max_pool_size}"
                )

                _mongo_client = AsyncIOMotorClient(
                    checkpoint_url,
                    maxPoolSize=mongo_max_pool_size,
                    minPoolSize=mongo_min_pool_size,
                )

                # Create the MongoDB checkpointer using the global client
                _mongo_checkpointer = AsyncMongoDBSaver(_mongo_client)
                await _mongo_checkpointer.setup()

                logger.info("Global MongoDB connection pool initialized successfully")
            except ImportError:
                logger.error("motor package not installed. Please install it with: pip install motor")
                raise RuntimeError("MongoDB checkpoint persistence is configured but the 'motor' package is not installed. Aborting startup.")
            except Exception as e:
                logger.error(f"Failed to initialize MongoDB connection pool: {e}")
                raise RuntimeError(f"MongoDB checkpoint persistence is configured but could not be initialized: {e}")

    # ========== YIELD - Application runs here ==========
    yield

    # ========== SHUTDOWN ==========
    # Close PostgreSQL connection pool
    if _pg_pool:
        logger.info("Closing global PostgreSQL connection pool")
        await _pg_pool.close()
        logger.info("Global PostgreSQL connection pool closed")

    # Close MongoDB connection
    if _mongo_client:
        logger.info("Closing global MongoDB connection")
        _mongo_client.close()
        logger.info("Global MongoDB connection closed")


app = FastAPI(
    title="DeerFlow API",
    description="API for Deer",
    version="0.1.0",
    lifespan=lifespan,
)

ecommerce_report_store = EcommerceReportStore()
ecommerce_batch_manager = EcommerceBatchTaskManager()


def _workspace_id(value: str | None) -> str:
    """Bound the local workspace identifier; this is not authentication."""

    candidate = (value or "local-user").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,80}", candidate):
        return "local-user"
    return candidate


_KNOWLEDGE_SUFFIXES = {".jsonl", ".ndjson", ".csv", ".md", ".markdown", ".txt"}


def _knowledge_file_path(owner_id: str, file_id: str) -> Path:
    """Resolve a previously uploaded private knowledge file safely."""

    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", file_id):
        raise HTTPException(status_code=400, detail="私有知识文件标识无效")
    path = Path("artifacts/ecommerce/knowledge") / owner_id / file_id
    if path.suffix.lower() not in _KNOWLEDGE_SUFFIXES or not path.is_file():
        raise HTTPException(status_code=404, detail="找不到当前工作区的私有知识文件")
    return path

# Add CORS middleware
# It's recommended to load the allowed origins from an environment variable
# for better security and flexibility across different environments.
allowed_origins_str = get_str_env(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
)
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]

logger.info(f"Allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Restrict to specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Use the configured list of methods
    allow_headers=["*"],  # Now allow all headers, but can be restricted further
)

_ECOMMERCE_PUBLIC_PATHS = {
    "/api/ecommerce/health",
    "/api/ecommerce/capabilities",
    "/api/ecommerce/authorized-data/adapters",
    "/api/ecommerce/demo/product-api",
    "/api/ecommerce/preflight",
    "/api/ecommerce/evaluation-summary",
    "/api/ecommerce/session",
}


@app.middleware("http")
async def ecommerce_workspace_auth(request, call_next):
    """Optionally enforce signed workspace tokens on stateful ecommerce APIs."""

    path = request.url.path
    public_path = path in _ECOMMERCE_PUBLIC_PATHS and not (
        path == "/api/ecommerce/session" and bearer_auth_required()
    )
    protected = path.startswith("/api/ecommerce/") and not public_path
    if protected and (workspace_token_required() or bearer_auth_required()):
        principal = None
        if bearer_auth_required():
            if oidc_provider_enabled():
                principal = decode_oidc_bearer_token(
                    request.headers.get("Authorization")
                )
            else:
                principal = decode_bearer_token(request.headers.get("Authorization"))
            if principal is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "需要有效的 Bearer JWT。"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            requested_workspace = request.headers.get("X-Workspace-Id", "").strip()
            if not requested_workspace or requested_workspace != principal.tenant_id:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "JWT 租户与工作区不匹配。"},
                )
        workspace_id = _workspace_id(request.headers.get("X-Workspace-Id"))
        token = request.headers.get("X-Workspace-Token")
        if workspace_token_required() and (
            not workspace_token_secret() or not verify_workspace_token(workspace_id, token)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "需要有效的工作区访问令牌。请先调用 /api/ecommerce/session。"},
            )
        if principal is not None:
            request.state.tenant_principal = principal
    return await call_next(request)
# Load examples into RAG providers if configured
load_milvus_examples()
load_qdrant_examples()

in_memory_store = InMemoryStore()
graph = build_graph_with_memory()


def _ecommerce_web_payload(
    state: dict[str, Any],
    *,
    trace_id: str | None = None,
) -> dict[str, Any]:
    report = state["ecommerce_report"]
    metrics = state.get("ecommerce_metrics", {})
    quality_audit = audit_report_payload(
        {
            "report": report,
            "run_metrics": metrics,
            "search_details": state.get("ecommerce_search_details", {}),
        }
    )
    return {
        "status": "success",
        "report": report,
        "report_markdown": state.get("final_report", ""),
        "report_html": render_html_report(
            report,
            search_status=str(state.get("ecommerce_search_status", "not_used")),
            model_status=str(metrics.get("model_status", "not_used")),
        ),
        "candidate_catalog": build_candidate_catalog(report),
        "report_fingerprint": state.get("ecommerce_report_fingerprint"),
        "search_status": state.get("ecommerce_search_status", "not_used"),
        "search_details": state.get("ecommerce_search_details", {}),
        "knowledge_status": state.get("ecommerce_knowledge_status", "not_used"),
        "knowledge_details": state.get("ecommerce_knowledge_details", {}),
        "agent_plan": state.get("ecommerce_agent_plan", []),
        "agent_results": state.get("ecommerce_agent_results", {}),
        "progress_events": state.get("ecommerce_progress_events", []),
        "model_status": metrics.get("model_status", "not_used"),
        "metrics": metrics,
        "report_quality_gates": metrics.get("report_quality_gates", {}),
        "citation_validation": state.get("ecommerce_citation_validation", {}),
        "verification_validation": state.get("ecommerce_verification_validation", {}),
        "quality_audit": quality_audit,
        "trace_id": trace_id,
    }


def _ecommerce_request_payload(
    request: EcommerceWebResearchRequest,
    *,
    owner_id: str = "local-user",
) -> dict[str, Any]:
    credentials = runtime_credentials(request.byok)
    payload: dict[str, Any] = {
        "category": request.category,
        "target_market": request.market,
        "price_min": request.price_min,
        "price_max": request.price_max,
        "top_n": request.top_n,
        "search_enabled": request.mode == "live",
        "model_config": {"enabled": request.model != "mock", "provider": request.model},
        "search_config": {
            "timeout": request.search_timeout,
            "max_retries": request.search_retries,
            "parallel_modules": request.search_parallel,
        },
        "data_config": {"provider": request.data_source},
    }
    if request.customer:
        payload["target_customer"] = request.customer
    if request.search_provider:
        payload["search_config"]["provider"] = request.search_provider
    if request.search_endpoint:
        payload["search_config"]["endpoint"] = request.search_endpoint
    if credentials:
        # Internal-only runtime data; the graph scrubs it before returning state.
        payload["_ecommerce_runtime_credentials"] = credentials
    if request.knowledge_file_id:
        payload["knowledge_config"] = {
            "path": str(_knowledge_file_path(owner_id, request.knowledge_file_id)),
            "retrieval_mode": "keyword",
            "top_k": 3,
        }
    return payload


def _execute_ecommerce_job(
    request: EcommerceWebResearchRequest,
    *,
    owner_id: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    state = run_ecommerce_graph(_ecommerce_request_payload(request, owner_id=owner_id))
    result = _ecommerce_web_payload(state, trace_id=trace_id or uuid4().hex)
    history_id = ecommerce_report_store.save(result, owner_id=owner_id)
    result["history_id"] = history_id
    result["history"] = {"history_id": history_id, "owner_id": owner_id}
    return result


def _run_batch_item(
    spec: dict[str, Any],
    item_id: str,
    *,
    owner_id: str,
) -> dict[str, Any]:
    """Run one independent batch item and return only a safe summary."""

    request = EcommerceWebResearchRequest.model_validate(spec)
    result = _execute_ecommerce_job(request, owner_id=owner_id)
    report = result.get("report", {})
    recommendations = report.get("recommendations", [])
    scores = [
        float(item.get("score", {}).get("total", 0))
        for item in recommendations
    ]
    return {
        "item_id": item_id,
        "history_id": result["history_id"],
        "average_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "recommendation_count": len(recommendations),
        "candidate_count": len(result.get("candidate_catalog", {}).get("candidates", [])),
        "search_status": result.get("search_status", "not_used"),
        "model_status": result.get("model_status", "not_used"),
    }


@app.get("/api/ecommerce/health")
async def ecommerce_health():
    """Health check for the interactive e-commerce workspace."""

    capabilities = build_ecommerce_capabilities()
    deepseek_capability = next(
        item for item in capabilities["models"] if item["id"] == "deepseek"
    )
    return {
        "status": "ok",
        "service": "ecommerce-workspace",
        "mock_available": True,
        "live_search_available": any(
            bool(item["configured"]) for item in capabilities["search_providers"]
        ),
        "deepseek_available": bool(deepseek_capability["configured"]),
        "capabilities_endpoint": "/api/ecommerce/capabilities",
        "preflight_endpoint": "/api/ecommerce/preflight",
        "rate_limiter": {
            "limit": _ecommerce_rate_limiter.limit,
            "window_seconds": _ecommerce_rate_limiter.window_seconds,
        },
        "circuit_breaker": _ecommerce_circuit_breaker.to_dict(),
        "observation_event_count": len(_ecommerce_observations),
    }


@app.get("/api/ecommerce/capabilities")
async def ecommerce_capabilities():
    """List selectable models and search providers without revealing secrets."""

    return {"status": "success", "capabilities": build_ecommerce_capabilities()}


@app.get("/api/ecommerce/authorized-data/adapters")
async def ecommerce_authorized_data_adapters():
    """List allowlisted user-owned data adapter contracts without secrets."""

    return {"status": "success", "adapters": list_authorized_adapters()}


@app.post("/api/ecommerce/preflight")
async def ecommerce_preflight(request: EcommercePreflightRequest):
    """Check external connectivity only when the caller explicitly requests it."""

    checks: dict[str, dict[str, Any]] = {}
    if request.provider in {"all", "search"}:
        from src.ecommerce.search.preflight import run_search_preflight

        checks["search"] = await asyncio.to_thread(
            run_search_preflight,
            request.query,
            provider=request.search_provider,
            endpoint=request.search_endpoint,
            api_key=(runtime_credentials(request.byok).get("search") or {}).get("api_key"),
            timeout=request.timeout,
            max_results=request.max_results,
        )
    if request.provider in {"all", "model"}:
        checks["model"] = await asyncio.to_thread(
            run_model_preflight,
            request.model,
            runtime_config=runtime_credentials(request.byok).get("model") or None,
        )
    if request.provider in {"all", "data"}:
        data_preflight_kwargs = {
            "timeout": min(30, int(request.timeout)),
        }
        data_api_key = (runtime_credentials(request.byok).get("data") or {}).get("api_key")
        if data_api_key:
            data_preflight_kwargs["api_key"] = data_api_key
        checks["data"] = await asyncio.to_thread(
            run_infoquest_preflight,
            request.url,
            **data_preflight_kwargs,
        )
    failed = [name for name, check in checks.items() if check.get("status") != "success"]
    if not failed:
        status = "success"
    elif len(failed) == len(checks):
        status = "error"
    else:
        status = "partial"
    return {"status": status, "checks": checks, "failed": failed}


@app.get("/api/ecommerce/observability")
async def ecommerce_observability(limit: int = Query(default=20, ge=0, le=200)):
    """Expose bounded local workflow events for diagnostics and demo use."""

    events = _ecommerce_observations.events()
    durations = sorted(
        float(event.duration_ms)
        for event in events
        if event.duration_ms is not None and event.duration_ms >= 0
    )
    status_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    for event in events:
        status_counts[event.status] = status_counts.get(event.status, 0) + 1
        if event.error_kind:
            error_counts[event.error_kind] = error_counts.get(event.error_kind, 0) + 1
    p95_index = min(len(durations) - 1, max(0, int(len(durations) * 0.95) - 1))
    return {
        "events": [event.to_dict() for event in _ecommerce_observations.recent(limit)],
        "count": len(events),
        "summary": {
            "status_counts": status_counts,
            "error_counts": error_counts,
            "average_duration_ms": round(mean(durations), 2) if durations else 0.0,
            "p95_duration_ms": round(durations[p95_index], 2) if durations else 0.0,
            "traced_run_count": len({event.trace_id for event in events if event.trace_id}),
        },
        "circuit_breaker": _ecommerce_circuit_breaker.to_dict(),
    }


@app.get("/api/ecommerce/evaluation-summary")
async def ecommerce_evaluation_summary():
    """Return the checked-in, offline evaluation summary for the dashboard."""

    summary_path = Path("artifacts/evaluation/ecommerce-eval-v1-summary.json")
    if not summary_path.is_file():
        raise HTTPException(status_code=404, detail="评测摘要尚未生成")
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="评测摘要读取失败") from exc
    review_path = Path("artifacts/evaluation/ecommerce-eval-v1-human-review.jsonl")
    pending_reviews = 0
    if review_path.is_file():
        for line in review_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    if json.loads(line).get("review_status") == "pending":
                        pending_reviews += 1
                except json.JSONDecodeError:
                    continue
    payload["human_review_pending_count"] = pending_reviews
    payload["source"] = "offline-artifact"
    return payload


@app.post("/api/ecommerce/authorized-data/validate")
async def ecommerce_authorized_data_validate(
    request: AuthorizedDataValidationRequest,
    x_workspace_id: str | None = Header(default=None),
):
    """Validate user-supplied authorized records without fetching external data."""

    owner_id = _workspace_id(x_workspace_id)
    if request.source.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="数据源不属于当前工作区")
    try:
        source = AuthorizedDataSource.model_validate(request.source.model_dump())
        records = [AuthorizedProductRecord.model_validate(item) for item in request.records]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="授权数据格式校验失败") from exc
    return validate_authorized_dataset(
        source,
        records,
        max_age_hours=request.max_age_hours,
    )


@app.post("/api/ecommerce/authorized-data/product-api/preflight")
async def ecommerce_product_api_preflight(
    request: ProductApiPreflightRequest,
    x_workspace_id: str | None = Header(default=None),
):
    """Read a bounded product sample from a user-authorized API.

    Credentials are request-scoped and the response is normalized before it
    leaves the server. This endpoint is a connection/data-shape check; it
    never opens the commercial decision gate.
    """

    owner_id = _workspace_id(x_workspace_id)
    try:
        config = ProductApiConfig.model_validate(request.config.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="商品 API 配置或安全策略校验失败") from exc
    return await asyncio.to_thread(probe_product_api, config, owner_id=owner_id)


@app.get("/api/ecommerce/demo/product-api")
async def ecommerce_demo_product_api(
    q: str = Query(default="可折叠露营桌", min_length=1, max_length=120),
):
    """Return deterministic, clearly-labelled product API data for demos.

    This endpoint is intentionally not presented as marketplace truth. It is a
    local adapter fixture so a presenter can demonstrate the user-configured
    API workflow without owning a commercial product-data credential.
    """

    samples = [
        {
            "id": "demo-api-001",
            "name": f"轻量铝合金{q}",
            "price": 159,
            "url": "https://demo.invalid/products/demo-api-001",
            "source": "DEMO_ONLY local product API",
        },
        {
            "id": "demo-api-002",
            "name": f"加厚便携{q}",
            "price": 229,
            "url": "https://demo.invalid/products/demo-api-002",
            "source": "DEMO_ONLY local product API",
        },
        {
            "id": "demo-api-003",
            "name": f"家庭套装{q}",
            "price": 299,
            "url": "https://demo.invalid/products/demo-api-003",
            "source": "DEMO_ONLY local product API",
        },
    ]
    return {
        "status": "success",
        "provider": "DeerFlow Demo Product API",
        "demo_only": True,
        "query": q,
        "data": samples,
    }


@app.post("/api/ecommerce/knowledge/upload")
async def ecommerce_knowledge_upload(
    file: UploadFile,
    x_workspace_id: str | None = Header(default=None),
):
    """Store a local private-knowledge file for the current anonymous workspace."""

    filename = _sanitize_filename(file.filename or "knowledge.txt")
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in _KNOWLEDGE_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="仅支持 .jsonl、.ndjson、.csv、.md、.markdown 和 .txt",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="私有知识文件为空")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="私有知识文件不能超过 10 MB")
    owner_id = _workspace_id(x_workspace_id)
    file_id = f"{uuid4().hex}{suffix}"
    target_dir = Path("artifacts/ecommerce/knowledge") / owner_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / file_id
    target.write_bytes(content)
    try:
        from src.ecommerce.knowledge.retriever import load_knowledge_records

        record_count = len(load_knowledge_records(target))
    except (OSError, ValueError) as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"私有知识文件无法解析：{exc}") from exc
    return {
        "status": "success",
        "filename": filename,
        "knowledge_file_id": file_id,
        "record_count": record_count,
        "size_bytes": len(content),
        "source_type": "local",
    }


@app.get("/ecommerce", response_class=HTMLResponse)
@app.get("/ecommerce/", response_class=HTMLResponse)
async def ecommerce_fallback_ui():
    """Serve a dependency-free fallback when the Next.js UI is unavailable."""
    return HTMLResponse(content=ECOMMERCE_FALLBACK_HTML)


@app.post("/api/ecommerce/research")
async def ecommerce_research(
    request: EcommerceWebResearchRequest,
    x_workspace_id: str | None = Header(default=None),
):
    """Run one e-commerce research job for the interactive web demo."""

    owner_id = _workspace_id(x_workspace_id)
    trace_id = uuid4().hex
    try:
        _ecommerce_rate_limiter.acquire_or_raise(owner_id)
    except RateLimitExceeded as exc:
        _ecommerce_observations.record(
            ObservationEvent(
                name="ecommerce.research",
                kind="request",
                status="rejected",
                error_kind=exc.error_kind,
                attributes={"workspace_id": owner_id},
                trace_id=trace_id,
            )
        )
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后重试。",
            headers={"Retry-After": str(max(1, int(exc.retry_after)))}
        ) from exc
    try:
        _ecommerce_circuit_breaker.before_call()
    except CircuitOpenError as exc:
        _ecommerce_observations.record(
            ObservationEvent(
                name="ecommerce.research",
                kind="request",
                status="rejected",
                error_kind=exc.error_kind,
                attributes={"workspace_id": owner_id, "circuit_state": exc.state},
                trace_id=trace_id,
            )
        )
        raise HTTPException(
            status_code=503,
            detail="研究服务暂时熔断，请稍后重试。",
            headers={"Retry-After": str(max(1, int(exc.retry_after)))}
        ) from exc

    started = perf_counter()
    _ecommerce_observations.record(
        ObservationEvent(
            name="ecommerce.research",
            kind="request",
            status="started",
            attributes={"workspace_id": owner_id, "mode": request.mode},
            trace_id=trace_id,
        )
    )
    try:
        result = _execute_ecommerce_job(request, owner_id=owner_id, trace_id=trace_id)
        history_id = result["history_id"]
        _ecommerce_circuit_breaker.record_success()
        _ecommerce_observations.record(
            ObservationEvent(
                name="ecommerce.research",
                kind="request",
                status="success",
                duration_ms=(perf_counter() - started) * 1000,
                attributes={
                    "workspace_id": owner_id,
                    "mode": request.mode,
                    "history_id": history_id,
                    "quality_status": result.get("quality_audit", {}).get("status"),
                },
                trace_id=trace_id,
            )
        )
        return result
    except Exception as exc:  # noqa: BLE001 - convert to safe API response
        _ecommerce_circuit_breaker.record_failure(exc)
        _ecommerce_observations.record(
            ObservationEvent(
                name="ecommerce.research",
                kind="request",
                status="error",
                duration_ms=(perf_counter() - started) * 1000,
                error_kind=classify_failure(exc),
                attributes={"workspace_id": owner_id, "mode": request.mode},
                trace_id=trace_id,
            )
        )
        logger.exception("Interactive e-commerce research failed")
        raise HTTPException(
            status_code=500,
            detail="电商研究运行失败，请检查后端日志和模型/搜索配置。",
        ) from exc


@app.post("/api/ecommerce/batch")
async def ecommerce_batch_research(
    request: EcommerceBatchResearchRequest,
    x_workspace_id: str | None = Header(default=None),
):
    """Queue independent category research jobs with bounded concurrency."""

    owner_id = _workspace_id(x_workspace_id)
    item_specs = [
        {
            **item.model_dump(mode="json"),
            "mode": request.mode,
            "model": request.model,
            "search_parallel": request.search_parallel,
            "search_timeout": request.search_timeout,
            "search_retries": request.search_retries,
            "data_source": request.data_source,
            "search_provider": request.search_provider,
            "search_endpoint": request.search_endpoint,
            "byok": request.byok,
        }
        for item in request.items
    ]
    task = ecommerce_batch_manager.create(
        owner_id=owner_id,
        item_specs=item_specs,
        mode=request.mode,
        model=request.model,
        max_concurrency=request.max_concurrency,
    )
    ecommerce_batch_manager.submit(
        task["task_id"],
        lambda spec, item_id: _run_batch_item(spec, item_id, owner_id=owner_id),
    )
    task = ecommerce_batch_manager.get(task["task_id"]) or task
    return {"status": "accepted", "task": task}


def _batch_task_for_owner(task_id: str, owner_id: str) -> dict[str, Any]:
    task = ecommerce_batch_manager.get(task_id)
    if task is None or task.get("owner_id") != owner_id:
        raise HTTPException(status_code=404, detail="找不到当前工作区的批量任务")
    return task


@app.get("/api/ecommerce/batch/{task_id}")
async def ecommerce_batch_status(
    task_id: str,
    x_workspace_id: str | None = Header(default=None),
):
    return {"status": "success", "task": _batch_task_for_owner(task_id, _workspace_id(x_workspace_id))}


@app.post("/api/ecommerce/batch/{task_id}/cancel")
async def ecommerce_batch_cancel(
    task_id: str,
    x_workspace_id: str | None = Header(default=None),
):
    owner_id = _workspace_id(x_workspace_id)
    _batch_task_for_owner(task_id, owner_id)
    task = ecommerce_batch_manager.cancel(task_id)
    return {"status": "success", "task": task}


@app.post("/api/ecommerce/batch/{task_id}/retry")
async def ecommerce_batch_retry(
    task_id: str,
    x_workspace_id: str | None = Header(default=None),
):
    owner_id = _workspace_id(x_workspace_id)
    task = _batch_task_for_owner(task_id, owner_id)
    failed = ecommerce_batch_manager.specs_for_failed_items(task_id)
    if failed is None or not failed[1]:
        raise HTTPException(status_code=400, detail="当前批量任务没有可重试的失败项")
    retry_task = ecommerce_batch_manager.create(
        owner_id=owner_id,
        item_specs=failed[1],
        mode=str(task["mode"]),
        model=str(task["model"]),
        max_concurrency=int(task["max_concurrency"]),
    )
    ecommerce_batch_manager.submit(
        retry_task["task_id"],
        lambda spec, item_id: _run_batch_item(spec, item_id, owner_id=owner_id),
    )
    return {
        "status": "accepted",
        "source_task_id": task_id,
        "task": ecommerce_batch_manager.get(retry_task["task_id"]) or retry_task,
    }


@app.get("/api/ecommerce/history")
async def ecommerce_history(
    limit: int = Query(default=30, ge=1, le=100),
    x_workspace_id: str | None = Header(default=None),
):
    """List saved local reports for one workspace."""

    return {
        "status": "success",
        "workspace_id": _workspace_id(x_workspace_id),
        "reports": ecommerce_report_store.list(
            owner_id=_workspace_id(x_workspace_id), limit=limit
        ),
    }


@app.get("/api/ecommerce/session")
async def ecommerce_session(x_workspace_id: str | None = Header(default=None)):
    """Expose the current anonymous workspace boundary for local demos.

    This is intentionally not authentication. A production deployment should
    replace the header-derived owner with a verified user identity.
    """

    workspace_id = _workspace_id(x_workspace_id)
    token = issue_workspace_token(workspace_id)
    return {
        "status": "success",
        "workspace_id": workspace_id,
        "workspace_token": token,
        "auth_mode": workspace_auth_mode(),
        "auth_ready": bool(token and workspace_token_required()),
        "identity_provider_required": True,
    }


@app.get("/api/ecommerce/history/{history_id}")
async def ecommerce_history_detail(
    history_id: str,
    x_workspace_id: str | None = Header(default=None),
):
    payload = ecommerce_report_store.get(
        history_id, owner_id=_workspace_id(x_workspace_id)
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="找不到当前工作区的报告快照")
    return payload


@app.post("/api/ecommerce/history/{history_id}/replay")
async def ecommerce_history_replay(
    history_id: str,
    x_workspace_id: str | None = Header(default=None),
):
    payload = ecommerce_report_store.get(
        history_id, owner_id=_workspace_id(x_workspace_id)
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="找不到当前工作区的报告快照")
    payload["replayed"] = True
    payload["replay_note"] = "本次回放未调用搜索或模型 API。"
    return payload


@app.post("/api/ecommerce/compare")
async def ecommerce_compare(
    request: EcommerceCompareRequest,
    x_workspace_id: str | None = Header(default=None),
):
    return ecommerce_report_store.compare(
        request.report_ids, owner_id=_workspace_id(x_workspace_id)
    )


@app.post("/api/ecommerce/excel/preview")
async def ecommerce_excel_preview(file: UploadFile):
    """Preview an Excel/CSV file before it is bound to a specific report."""

    filename = _sanitize_filename(file.filename or "upload.xlsx")
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in {".xlsx", ".xlsm", ".xls", ".csv", ".tsv"}:
        raise HTTPException(status_code=400, detail="仅支持 .xlsx、.xlsm、.xls、.csv 和 .tsv")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 20 MB")
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(content)
            temporary_path = temporary.name
        return {
            "status": "success",
            "filename": filename,
            "preview": preview_import_file(temporary_path),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                logger.warning("Could not remove temporary Excel preview file")


def _parse_excel_mapping(mapping_json: str) -> dict[str, str]:
    try:
        payload = json.loads(mapping_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="字段映射必须是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="字段映射必须是对象")
    return {str(key): str(value) for key, value in payload.items() if value}


async def _store_excel_upload(file: UploadFile) -> tuple[str, bytes, str]:
    filename = _sanitize_filename(file.filename or "upload.xlsx")
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in {".xlsx", ".xlsm", ".xls", ".csv", ".tsv"}:
        raise HTTPException(status_code=400, detail="仅支持 .xlsx、.xlsm、.xls、.csv 和 .tsv")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 20 MB")
    return filename, content, suffix


async def _excel_result_for_report(
    file: UploadFile,
    *,
    report_id: str,
    owner_id: str,
    mapping_json: str,
):
    payload = ecommerce_report_store.get(report_id, owner_id=owner_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="找不到要绑定 Excel 的报告快照")
    filename, content, suffix = await _store_excel_upload(file)
    mapping = _parse_excel_mapping(mapping_json)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(content)
            temporary_path = temporary.name
        result = import_verification_rows(
            temporary_path,
            payload["report"],
            column_mapping=mapping,
            default_run_id=report_id,
        )
        return filename, result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                logger.warning("Could not remove temporary Excel validation file")


@app.post("/api/ecommerce/excel/validate")
async def ecommerce_excel_validate(
    file: UploadFile,
    report_id: str = Form(...),
    mapping_json: str = Form(default="{}"),
    x_workspace_id: str | None = Header(default=None),
):
    """Validate mapped Excel rows against a saved report without importing them."""

    filename, result = await _excel_result_for_report(
        file,
        report_id=report_id,
        owner_id=_workspace_id(x_workspace_id),
        mapping_json=mapping_json,
    )
    return {
        "status": "success" if result.complete else "blocked",
        "filename": filename,
        "validation": result.as_dict(),
        "records": [record.model_dump(mode="json") for record in result.records],
    }


@app.post("/api/ecommerce/excel/import")
async def ecommerce_excel_import(
    file: UploadFile,
    report_id: str = Form(...),
    mapping_json: str = Form(default="{}"),
    confirm: bool = Form(default=False),
    x_workspace_id: str | None = Header(default=None),
):
    """Validate and confirm a local commercial-data import for one report."""

    owner_id = _workspace_id(x_workspace_id)
    filename, result = await _excel_result_for_report(
        file,
        report_id=report_id,
        owner_id=owner_id,
        mapping_json=mapping_json,
    )
    validation = result.as_dict()
    if not confirm:
        return {
            "status": "confirmation_required",
            "filename": filename,
            "validation": validation,
            "message": "校验通过后再次提交并勾选确认，系统才会写入本地导入审计快照。",
        }
    if not result.complete:
        raise HTTPException(
            status_code=400,
            detail={"message": "Excel 校验未通过，不能确认导入。", "validation": validation},
        )
    target_dir = Path("artifacts/ecommerce/imports") / re.sub(r"[^A-Za-z0-9_-]", "_", owner_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_report_id = re.sub(r"[^A-Za-z0-9_-]", "_", report_id)
    target = target_dir / f"{safe_report_id}.json"
    target.write_text(
        json.dumps(
            {
                "report_id": report_id,
                "owner_id": owner_id,
                "filename": filename,
                "validation": validation,
                "records": [record.model_dump(mode="json") for record in result.records],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "status": "success",
        "filename": filename,
        "imported_count": len(result.records),
        "validation": validation,
        "artifact_path": str(target),
    }


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    # Check if MCP server configuration is enabled
    mcp_enabled = get_bool_env("ENABLE_MCP_SERVER_CONFIGURATION", False)

    logger.debug(f"get the request locale : {request.locale}")

    # Validate MCP settings if provided
    if request.mcp_settings and not mcp_enabled:
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is disabled. Set ENABLE_MCP_SERVER_CONFIGURATION=true to enable MCP features.",
        )

    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())

    return StreamingResponse(
        _astream_workflow_generator(
            request.model_dump()["messages"],
            thread_id,
            request.resources,
            request.max_plan_iterations,
            request.max_step_num,
            request.max_search_results,
            request.auto_accepted_plan,
            request.interrupt_feedback,
            request.mcp_settings if mcp_enabled else {},
            request.enable_background_investigation,
            request.enable_web_search,
            request.report_style,
            request.enable_deep_thinking,
            request.enable_clarification,
            request.max_clarification_rounds,
            request.locale,
            request.interrupt_before_tools,
        ),
        media_type="text/event-stream",
    )


def _validate_tool_call_chunks(tool_call_chunks):
    """Validate and log tool call chunk structure for debugging."""
    if not tool_call_chunks:
        return

    logger.debug(f"Validating tool_call_chunks: count={len(tool_call_chunks)}")

    indices_seen = set()
    tool_ids_seen = set()

    for i, chunk in enumerate(tool_call_chunks):
        index = chunk.get("index")
        tool_id = chunk.get("id")
        name = chunk.get("name", "")
        has_args = "args" in chunk

        logger.debug(
            f"Chunk {i}: index={index}, id={tool_id}, name={name}, "
            f"has_args={has_args}, type={chunk.get('type')}"
        )

        if index is not None:
            indices_seen.add(index)
        if tool_id:
            tool_ids_seen.add(tool_id)

    if len(indices_seen) > 1:
        logger.debug(
            f"Multiple indices detected: {sorted(indices_seen)} - "
            f"This may indicate consecutive tool calls"
        )


def _process_tool_call_chunks(tool_call_chunks):
    """
    Process tool call chunks with proper index-based grouping.

    This function handles the concatenation of tool call chunks that belong
    to the same tool call (same index) while properly segregating chunks
    from different tool calls (different indices).

    The issue: In streaming, LangChain's ToolCallChunk concatenates string
    attributes (name, args) when chunks have the same index. We need to:
    1. Group chunks by index
    2. Detect index collisions with different tool names
    3. Accumulate arguments for the same index
    4. Return properly segregated tool calls
    """
    if not tool_call_chunks:
        return []

    _validate_tool_call_chunks(tool_call_chunks)

    chunks = []
    chunk_by_index = {}  # Group chunks by index to handle streaming accumulation

    for chunk in tool_call_chunks:
        index = chunk.get("index")
        chunk_id = chunk.get("id")

        if index is not None:
            # Create or update entry for this index
            if index not in chunk_by_index:
                chunk_by_index[index] = {
                    "name": "",
                    "args": "",
                    "id": chunk_id or "",
                    "index": index,
                    "type": chunk.get("type", ""),
                }

            # Validate and accumulate tool name
            chunk_name = chunk.get("name", "")
            if chunk_name:
                stored_name = chunk_by_index[index]["name"]

                # Check for index collision with different tool names
                if stored_name and stored_name != chunk_name:
                    logger.warning(
                        f"Tool name mismatch detected at index {index}: "
                        f"'{stored_name}' != '{chunk_name}'. "
                        f"This may indicate a streaming artifact or consecutive tool calls "
                        f"with the same index assignment."
                    )
                    # Keep the first name to prevent concatenation
                else:
                    chunk_by_index[index]["name"] = chunk_name

            # Update ID if new one provided
            if chunk_id and not chunk_by_index[index]["id"]:
                chunk_by_index[index]["id"] = chunk_id

            # Accumulate arguments
            if chunk.get("args"):
                chunk_by_index[index]["args"] += chunk.get("args", "")
        else:
            # Handle chunks without explicit index (edge case)
            logger.debug(f"Chunk without index encountered: {chunk}")
            chunks.append({
                "name": chunk.get("name", ""),
                "args": sanitize_args(chunk.get("args", "")),
                "id": chunk.get("id", ""),
                "index": 0,
                "type": chunk.get("type", ""),
            })

    # Convert indexed chunks to list, sorted by index for proper order
    for index in sorted(chunk_by_index.keys()):
        chunk_data = chunk_by_index[index]
        chunk_data["args"] = sanitize_args(chunk_data["args"])
        chunks.append(chunk_data)
        logger.debug(
            f"Processed tool call: index={index}, name={chunk_data['name']}, "
            f"id={chunk_data['id']}"
        )

    return chunks


def _get_agent_name(agent, message_metadata):
    """Extract agent name from agent tuple."""
    agent_name = "unknown"
    if agent and len(agent) > 0:
        agent_name = agent[0].split(":")[0] if ":" in agent[0] else agent[0]
    else:
        agent_name = message_metadata.get("langgraph_node", "unknown")
    return agent_name


def _create_event_stream_message(
    message_chunk, message_metadata, thread_id, agent_name
):
    """Create base event stream message."""
    content = message_chunk.content
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)

    # Strip <think>...</think> tags that some models (e.g. DeepSeek-R1, QwQ via ollama)
    # embed directly in content instead of using the reasoning_content field (#781)
    if isinstance(content, str) and "<think>" in content:
        content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()

    event_stream_message = {
        "thread_id": thread_id,
        "agent": agent_name,
        "id": message_chunk.id,
        "role": "assistant",
        "checkpoint_ns": message_metadata.get("checkpoint_ns", ""),
        "langgraph_node": message_metadata.get("langgraph_node", ""),
        "langgraph_path": message_metadata.get("langgraph_path", ""),
        "langgraph_step": message_metadata.get("langgraph_step", ""),
        "content": content,
    }

    # Add optional fields
    if message_chunk.additional_kwargs.get("reasoning_content"):
        event_stream_message["reasoning_content"] = message_chunk.additional_kwargs[
            "reasoning_content"
        ]

    if message_chunk.response_metadata.get("finish_reason"):
        event_stream_message["finish_reason"] = message_chunk.response_metadata.get(
            "finish_reason"
        )

    return event_stream_message


def _create_interrupt_event(thread_id, event_data):
    """Create interrupt event."""
    interrupt = event_data["__interrupt__"][0]
    # Use the 'id' attribute (LangGraph 1.0+) instead of deprecated 'ns[0]'
    interrupt_id = getattr(interrupt, "id", None) or thread_id
    return _make_event(
        "interrupt",
        {
            "thread_id": thread_id,
            "id": interrupt_id,
            "role": "assistant",
            "content": interrupt.value,
            "finish_reason": "interrupt",
            "options": [
                {"text": "Edit plan", "value": "edit_plan"},
                {"text": "Start research", "value": "accepted"},
            ],
        },
    )


def _process_initial_messages(message, thread_id):
    """Process initial messages and yield formatted events."""
    json_data = json.dumps(
        {
            "thread_id": thread_id,
            "id": "run--" + message.get("id", uuid4().hex),
            "role": "user",
            "content": message.get("content", ""),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    chat_stream_message(
        thread_id, f"event: message_chunk\ndata: {json_data}\n\n", "none"
    )


async def _process_message_chunk(message_chunk, message_metadata, thread_id, agent):
    """Process a single message chunk and yield appropriate events."""

    agent_name = _get_agent_name(agent, message_metadata)
    safe_agent_name = sanitize_agent_name(agent_name)
    safe_thread_id = sanitize_thread_id(thread_id)
    safe_agent = sanitize_agent_name(agent)
    logger.debug(f"[{safe_thread_id}] _process_message_chunk started for agent={safe_agent_name}")
    logger.debug(f"[{safe_thread_id}] Extracted agent_name: {safe_agent_name}")

    event_stream_message = _create_event_stream_message(
        message_chunk, message_metadata, thread_id, agent_name
    )

    if isinstance(message_chunk, ToolMessage):
        # Tool Message - Return the result of the tool call
        logger.debug(f"[{safe_thread_id}] Processing ToolMessage")
        tool_call_id = message_chunk.tool_call_id
        event_stream_message["tool_call_id"] = tool_call_id

        # Validate tool_call_id for debugging
        if tool_call_id:
            safe_tool_id = sanitize_log_input(tool_call_id, max_length=100)
            logger.debug(f"[{safe_thread_id}] ToolMessage with tool_call_id: {safe_tool_id}")
        else:
            logger.warning(f"[{safe_thread_id}] ToolMessage received without tool_call_id")

        logger.debug(f"[{safe_thread_id}] Yielding tool_call_result event")
        yield _make_event("tool_call_result", event_stream_message)
    elif isinstance(message_chunk, AIMessageChunk):
        # AI Message - Raw message tokens
        has_tool_calls = bool(message_chunk.tool_calls)
        has_chunks = bool(message_chunk.tool_call_chunks)
        logger.debug(f"[{safe_thread_id}] Processing AIMessageChunk, tool_calls={has_tool_calls}, tool_call_chunks={has_chunks}")

        if message_chunk.tool_calls:
            # AI Message - Tool Call (complete tool calls)
            safe_tool_names = [sanitize_tool_name(tc.get('name', 'unknown')) for tc in message_chunk.tool_calls]
            logger.debug(f"[{safe_thread_id}] AIMessageChunk has complete tool_calls: {safe_tool_names}")
            event_stream_message["tool_calls"] = message_chunk.tool_calls

            # Process tool_call_chunks with proper index-based grouping
            processed_chunks = _process_tool_call_chunks(
                message_chunk.tool_call_chunks
            )
            if processed_chunks:
                event_stream_message["tool_call_chunks"] = processed_chunks
                safe_chunk_names = [sanitize_tool_name(c.get('name')) for c in processed_chunks]
                logger.debug(
                    f"[{safe_thread_id}] Tool calls: {safe_tool_names}, "
                    f"Processed chunks: {len(processed_chunks)}"
                )

            logger.debug(f"[{safe_thread_id}] Yielding tool_calls event")
            yield _make_event("tool_calls", event_stream_message)
        elif message_chunk.tool_call_chunks:
            # AI Message - Tool Call Chunks (streaming)
            chunks_count = len(message_chunk.tool_call_chunks)
            logger.debug(f"[{safe_thread_id}] AIMessageChunk has streaming tool_call_chunks: {chunks_count} chunks")
            processed_chunks = _process_tool_call_chunks(
                message_chunk.tool_call_chunks
            )

            # Emit separate events for chunks with different indices (tool call boundaries)
            if processed_chunks:
                prev_chunk = None
                for chunk in processed_chunks:
                    current_index = chunk.get("index")

                    # Log index transitions to detect tool call boundaries
                    if prev_chunk is not None and current_index != prev_chunk.get("index"):
                        prev_name = sanitize_tool_name(prev_chunk.get('name'))
                        curr_name = sanitize_tool_name(chunk.get('name'))
                        logger.debug(
                            f"[{safe_thread_id}] Tool call boundary detected: "
                            f"index {prev_chunk.get('index')} ({prev_name}) -> "
                            f"{current_index} ({curr_name})"
                        )

                    prev_chunk = chunk

                # Include all processed chunks in the event
                event_stream_message["tool_call_chunks"] = processed_chunks
                safe_chunk_names = [sanitize_tool_name(c.get('name')) for c in processed_chunks]
                logger.debug(
                    f"[{safe_thread_id}] Streamed {len(processed_chunks)} tool call chunk(s): "
                    f"{safe_chunk_names}"
                )

            logger.debug(f"[{safe_thread_id}] Yielding tool_call_chunks event")
            yield _make_event("tool_call_chunks", event_stream_message)
        else:
            # AI Message - Raw message tokens
            content_len = len(message_chunk.content) if isinstance(message_chunk.content, str) else 0
            logger.debug(f"[{safe_thread_id}] AIMessageChunk is raw message tokens, content_len={content_len}")
            yield _make_event("message_chunk", event_stream_message)


def extract_citations_from_event(event: Any, safe_thread_id: str = "unknown") -> list:
    """Extract all citations from event data using an iterative, depth-limited traversal."""
    # Only dict-based event structures are supported
    if not isinstance(event, dict):
        return []

    from collections import deque
    citations: list[Any] = []
    max_depth = 5  # Prevent excessively deep traversal
    max_nodes = 5000  # Safety cap to avoid pathological large structures

    # Queue holds (node_dict, depth) for BFS traversal
    queue: deque[tuple[dict[str, Any], int]] = deque([(event, 0)])
    nodes_visited = 0

    while queue:
        current, depth = queue.popleft()
        nodes_visited += 1
        if nodes_visited > max_nodes:
            logger.warning(
                f"[{safe_thread_id}] Stopping citation extraction after visiting "
                f"{nodes_visited} nodes to avoid performance issues"
            )
            break

        # Direct citations field at this level
        direct_citations = current.get("citations")
        if isinstance(direct_citations, list) and direct_citations:
            logger.debug(
                f"[{safe_thread_id}] Found {len(direct_citations)} citations at depth {depth}"
            )
            citations.extend(direct_citations)

        # Do not traverse deeper than max_depth
        if depth >= max_depth:
            continue

        # Check nested values (for updates mode)
        for value in current.values():
            if isinstance(value, dict):
                queue.append((value, depth + 1))
            # Also check if the value is a list of dicts (like Command updates)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        queue.append((item, depth + 1))
    return citations


async def _stream_graph_events(
    graph_instance, workflow_input, workflow_config, thread_id
):
    """Stream events from the graph and process them."""
    safe_thread_id = sanitize_thread_id(thread_id)
    logger.debug(f"[{safe_thread_id}] Starting graph event stream with agent nodes")

    # Track citations collected during research
    collected_citations = []

    try:
        event_count = 0
        last_state_update = None  # Track the last state update to get final citations

        async for agent, _, event_data in graph_instance.astream(
            workflow_input,
            config=workflow_config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            event_count += 1
            safe_agent = sanitize_agent_name(agent)
            logger.debug(f"[{safe_thread_id}] Graph event #{event_count} received from agent: {safe_agent}")

            if isinstance(event_data, dict):
                # Store the last state update for final citation extraction
                last_state_update = event_data

                # Log event keys for debugging (more verbose for citations debugging)
                event_keys = list(event_data.keys())

                # Check for citations in state updates (may be nested)
                new_citations = extract_citations_from_event(event_data, safe_thread_id)
                if new_citations:
                    # Accumulate citations across events instead of overwriting
                    # using merge_citations to avoid duplicates and preserve better metadata
                    collected_citations = merge_citations(collected_citations, new_citations)
                    # Key difference: replace string heuristic with actual extraction count for logging
                    logger.info(
                        f"[{safe_thread_id}] Event contains citations, "
                        f"keys: {event_keys}, count: {len(new_citations)}, total: {len(collected_citations)}"
                    )

                if "__interrupt__" in event_data:
                    logger.debug(
                        f"[{safe_thread_id}] Processing interrupt event: "
                        f"id={getattr(event_data['__interrupt__'][0], 'id', 'unknown') if isinstance(event_data['__interrupt__'], (list, tuple)) and len(event_data['__interrupt__']) > 0 else 'unknown'}, "
                        f"value_len={len(getattr(event_data['__interrupt__'][0], 'value', '')) if isinstance(event_data['__interrupt__'], (list, tuple)) and len(event_data['__interrupt__']) > 0 and hasattr(event_data['__interrupt__'][0], 'value') and hasattr(event_data['__interrupt__'][0].value, '__len__') else 'unknown'}"
                    )
                    yield _create_interrupt_event(thread_id, event_data)
                logger.debug(f"[{safe_thread_id}] Dict event without interrupt, skipping")
                continue

            message_chunk, message_metadata = cast(
                tuple[BaseMessage, dict[str, Any]], event_data
            )

            safe_node = sanitize_agent_name(message_metadata.get('langgraph_node', 'unknown'))
            safe_step = sanitize_log_input(message_metadata.get('langgraph_step', 'unknown'))
            logger.debug(
                f"[{safe_thread_id}] Processing message chunk: "
                f"type={type(message_chunk).__name__}, "
                f"node={safe_node}, "
                f"step={safe_step}"
            )

            async for event in _process_message_chunk(
                message_chunk, message_metadata, thread_id, agent
            ):
                yield event

        # After streaming completes, try to get citations
        # First check if we collected any during streaming
        if not collected_citations and last_state_update:
            # Try to get citations from the last state update
            logger.debug(f"[{safe_thread_id}] No citations collected during streaming, checking last state update")
            collected_citations = extract_citations_from_event(last_state_update, safe_thread_id)

        # If still no citations, try to get from graph state directly
        if not collected_citations:
            try:
                # Get the current state from the graph using proper config
                state_config = {"configurable": {"thread_id": thread_id}}
                current_state = await graph_instance.aget_state(state_config)
                if current_state and hasattr(current_state, 'values'):
                    state_values = current_state.values
                    if isinstance(state_values, dict) and 'citations' in state_values:
                        collected_citations = state_values.get('citations', [])
                        logger.info(f"[{safe_thread_id}] Retrieved {len(collected_citations)} citations from final graph state")
            except Exception as e:
                logger.warning(
                    f"[{safe_thread_id}] Could not retrieve citations from graph state: {e}",
                    exc_info=True,
                )

        # Send collected citations as a separate event
        if collected_citations:
            logger.info(f"[{safe_thread_id}] Sending {len(collected_citations)} citations to client")
            yield _make_event("citations", {
                "thread_id": thread_id,
                "citations": collected_citations,
            })
        else:
            logger.debug(f"[{safe_thread_id}] No citations to send")

        logger.debug(f"[{safe_thread_id}] Graph event stream completed. Total events: {event_count}")
    except asyncio.CancelledError:
        # User cancelled/interrupted the stream - this is normal, not an error.
        # Do not re-raise: ending the generator gracefully lets FastAPI close the
        # HTTP response properly so the client won't see "error decoding response body".
        logger.info(f"[{safe_thread_id}] Graph event stream cancelled by user after {event_count} events")
        try:
            yield _make_event("error", {
                "thread_id": thread_id,
                "error": "Stream cancelled",
                "reason": "cancelled",
            })
        except Exception:
            pass  # Client likely already disconnected
        return
    except Exception as e:
        logger.exception(f"[{safe_thread_id}] Error during graph execution")
        yield _make_event(
            "error",
            {
                "thread_id": thread_id,
                "error": "Error during graph execution",
            },
        )


async def _astream_workflow_generator(
    messages: List[dict],
    thread_id: str,
    resources: List[Resource],
    max_plan_iterations: int,
    max_step_num: int,
    max_search_results: int,
    auto_accepted_plan: bool,
    interrupt_feedback: str,
    mcp_settings: dict,
    enable_background_investigation: bool,
    enable_web_search: bool,
    report_style: ReportStyle,
    enable_deep_thinking: bool,
    enable_clarification: bool,
    max_clarification_rounds: int,
    locale: str = "en-US",
    interrupt_before_tools: Optional[List[str]] = None,
):
    safe_thread_id = sanitize_thread_id(thread_id)
    safe_feedback = sanitize_log_input(interrupt_feedback) if interrupt_feedback else ""
    logger.debug(
        f"[{safe_thread_id}] _astream_workflow_generator starting: "
        f"messages_count={len(messages)}, "
        f"auto_accepted_plan={auto_accepted_plan}, "
        f"interrupt_feedback={safe_feedback}, "
        f"interrupt_before_tools={interrupt_before_tools}"
    )

    # Process initial messages
    logger.debug(f"[{safe_thread_id}] Processing {len(messages)} initial messages")
    for message in messages:
        if isinstance(message, dict) and "content" in message:
            safe_content = sanitize_user_content(message.get('content', ''))
            logger.debug(f"[{safe_thread_id}] Sending initial message to client: {safe_content}")
            _process_initial_messages(message, thread_id)

    logger.debug(f"[{safe_thread_id}] Reconstructing clarification history")
    clarification_history = reconstruct_clarification_history(messages)

    logger.debug(f"[{safe_thread_id}] Building clarified topic from history")
    clarified_topic, clarification_history = build_clarified_topic_from_history(
        clarification_history
    )
    latest_message_content = messages[-1]["content"] if messages else ""
    clarified_research_topic = clarified_topic or latest_message_content
    safe_topic = sanitize_user_content(clarified_research_topic)
    logger.debug(f"[{safe_thread_id}] Clarified research topic: {safe_topic}")

    # Prepare workflow input
    logger.debug(f"[{safe_thread_id}] Preparing workflow input")
    workflow_input = {
        "messages": messages,
        "plan_iterations": 0,
        "final_report": "",
        "current_plan": None,
        "observations": [],
        "auto_accepted_plan": auto_accepted_plan,
        "enable_background_investigation": enable_background_investigation,
        "research_topic": latest_message_content,
        "clarification_history": clarification_history,
        "clarified_research_topic": clarified_research_topic,
        "enable_clarification": enable_clarification,
        "max_clarification_rounds": max_clarification_rounds,
        "locale": locale,
    }

    if not auto_accepted_plan and interrupt_feedback:
        logger.debug(f"[{safe_thread_id}] Creating resume command with interrupt_feedback: {safe_feedback}")
        resume_msg = f"[{interrupt_feedback}]"
        if messages:
            resume_msg += f" {messages[-1]['content']}"
        workflow_input = Command(resume=resume_msg)

    # Prepare workflow config
    logger.debug(
        f"[{safe_thread_id}] Preparing workflow config: "
        f"max_plan_iterations={max_plan_iterations}, "
        f"max_step_num={max_step_num}, "
        f"report_style={report_style.value}, "
        f"enable_deep_thinking={enable_deep_thinking}"
    )
    workflow_config = {
        "thread_id": thread_id,
        "resources": resources,
        "max_plan_iterations": max_plan_iterations,
        "max_step_num": max_step_num,
        "max_search_results": max_search_results,
        "mcp_settings": mcp_settings,
        "enable_web_search": enable_web_search,
        "report_style": report_style.value,
        "enable_deep_thinking": enable_deep_thinking,
        "interrupt_before_tools": interrupt_before_tools,
        "recursion_limit": get_recursion_limit(),
    }

    checkpoint_saver = get_bool_env("LANGGRAPH_CHECKPOINT_SAVER", False)
    checkpoint_url = get_str_env("LANGGRAPH_CHECKPOINT_DB_URL", "")

    logger.debug(
        f"[{safe_thread_id}] Checkpoint configuration: "
        f"saver_enabled={checkpoint_saver}, "
        f"url_configured={bool(checkpoint_url)}"
    )

    # Handle checkpointer if configured - prefer global connection pools
    if checkpoint_saver and checkpoint_url != "":
        # Try to use global PostgreSQL checkpointer first
        if checkpoint_url.startswith("postgresql://") and _pg_checkpointer:
            logger.info(f"[{safe_thread_id}] Using global PostgreSQL connection pool")
            graph.checkpointer = _pg_checkpointer
            graph.store = in_memory_store
            logger.debug(f"[{safe_thread_id}] Starting to stream graph events")
            async for event in _stream_graph_events(
                graph, workflow_input, workflow_config, thread_id
            ):
                yield event
            logger.debug(f"[{safe_thread_id}] Graph event streaming completed")

        # Fallback to per-request PostgreSQL connection if global pool not available
        elif checkpoint_url.startswith("postgresql://"):
            logger.info(f"[{safe_thread_id}] Global pool unavailable, creating per-request PostgreSQL connection")
            connection_kwargs = {
                "autocommit": True,
                "row_factory": "dict_row",
                "prepare_threshold": 0,
            }
            async with AsyncConnectionPool(
                checkpoint_url, kwargs=connection_kwargs
            ) as conn:
                checkpointer = AsyncPostgresSaver(conn)
                await checkpointer.setup()
                graph.checkpointer = checkpointer
                graph.store = in_memory_store
                logger.debug(f"[{safe_thread_id}] Starting to stream graph events")
                async for event in _stream_graph_events(
                    graph, workflow_input, workflow_config, thread_id
                ):
                    yield event
                logger.debug(f"[{safe_thread_id}] Graph event streaming completed")

        # Try to use global MongoDB checkpointer first
        elif checkpoint_url.startswith("mongodb://") and _mongo_checkpointer:
            logger.info(f"[{safe_thread_id}] Using global MongoDB connection pool")
            graph.checkpointer = _mongo_checkpointer
            graph.store = in_memory_store
            logger.debug(f"[{safe_thread_id}] Starting to stream graph events")
            async for event in _stream_graph_events(
                graph, workflow_input, workflow_config, thread_id
            ):
                yield event
            logger.debug(f"[{safe_thread_id}] Graph event streaming completed")

        # Fallback to per-request MongoDB connection if global pool not available
        elif checkpoint_url.startswith("mongodb://"):
            logger.info(f"[{safe_thread_id}] Global pool unavailable, creating per-request MongoDB connection")
            async with AsyncMongoDBSaver.from_conn_string(
                checkpoint_url
            ) as checkpointer:
                graph.checkpointer = checkpointer
                graph.store = in_memory_store
                logger.debug(f"[{safe_thread_id}] Starting to stream graph events")
                async for event in _stream_graph_events(
                    graph, workflow_input, workflow_config, thread_id
                ):
                    yield event
                logger.debug(f"[{safe_thread_id}] Graph event streaming completed")
    else:
        logger.debug(f"[{safe_thread_id}] No checkpointer configured, using in-memory graph")
        # Use graph without checkpointer
        logger.debug(f"[{safe_thread_id}] Starting to stream graph events")
        async for event in _stream_graph_events(
            graph, workflow_input, workflow_config, thread_id
        ):
            yield event
        logger.debug(f"[{safe_thread_id}] Graph event streaming completed")


def _make_event(event_type: str, data: dict[str, any]):
    if data.get("content") == "":
        data.pop("content")
    # Ensure JSON serialization with proper encoding
    try:
        json_data = json.dumps(data, ensure_ascii=False)

        finish_reason = data.get("finish_reason", "")
        chat_stream_message(
            data.get("thread_id", ""),
            f"event: {event_type}\ndata: {json_data}\n\n",
            finish_reason,
        )

        return f"event: {event_type}\ndata: {json_data}\n\n"
    except (TypeError, ValueError) as e:
        logger.error(f"Error serializing event data: {e}")
        # Return a safe error event
        error_data = json.dumps({"error": "Serialization failed"}, ensure_ascii=False)
        return f"event: error\ndata: {error_data}\n\n"


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using volcengine TTS API."""
    app_id = get_str_env("VOLCENGINE_TTS_APPID", "")
    if not app_id:
        raise HTTPException(status_code=400, detail="VOLCENGINE_TTS_APPID is not set")
    access_token = get_str_env("VOLCENGINE_TTS_ACCESS_TOKEN", "")
    if not access_token:
        raise HTTPException(
            status_code=400, detail="VOLCENGINE_TTS_ACCESS_TOKEN is not set"
        )

    try:
        cluster = get_str_env("VOLCENGINE_TTS_CLUSTER", "volcano_tts")
        voice_type = get_str_env("VOLCENGINE_TTS_VOICE_TYPE", "BV700_V2_streaming")

        tts_client = VolcengineTTS(
            appid=app_id,
            access_token=access_token,
            cluster=cluster,
            voice_type=voice_type,
        )
        # Call the TTS API
        result = tts_client.text_to_speech(
            text=request.text[:1024],
            encoding=request.encoding,
            speed_ratio=request.speed_ratio,
            volume_ratio=request.volume_ratio,
            pitch_ratio=request.pitch_ratio,
            text_type=request.text_type,
            with_frontend=request.with_frontend,
            frontend_type=request.frontend_type,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=str(result["error"]))

        # Decode the base64 audio data
        audio_data = base64.b64decode(result["audio_data"])

        # Return the audio file
        return Response(
            content=audio_data,
            media_type=f"audio/{request.encoding}",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=tts_output.{request.encoding}"
                )
            },
        )

    except Exception as e:
        logger.exception(f"Error in TTS endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/podcast/generate")
async def generate_podcast(request: GeneratePodcastRequest):
    try:
        report_content = request.content
        print(report_content)
        workflow = build_podcast_graph()
        final_state = workflow.invoke({"input": report_content})
        audio_bytes = final_state["output"]
        return Response(content=audio_bytes, media_type="audio/mp3")
    except Exception as e:
        logger.exception(f"Error occurred during podcast generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/ppt/generate")
async def generate_ppt(request: GeneratePPTRequest):
    try:
        report_content = request.content
        print(report_content)
        workflow = build_ppt_graph()
        final_state = workflow.invoke({"input": report_content, "locale": request.locale})
        generated_file_path = final_state["generated_file_path"]
        with open(generated_file_path, "rb") as f:
            ppt_bytes = f.read()
        return Response(
            content=ppt_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except Exception as e:
        logger.exception(f"Error occurred during ppt generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/prose/generate")
async def generate_prose(request: GenerateProseRequest):
    try:
        sanitized_prompt = request.prompt.replace("\r\n", "").replace("\n", "")
        logger.info(f"Generating prose for prompt: {sanitized_prompt}")
        workflow = build_prose_graph()
        events = workflow.astream(
            {
                "content": request.prompt,
                "option": request.option,
                "command": request.command,
            },
            stream_mode="messages",
            subgraphs=True,
        )
        return StreamingResponse(
            (f"data: {event[0].content}\n\n" async for _, event in events),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.exception(f"Error occurred during prose generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/report/evaluate", response_model=EvaluateReportResponse)
async def evaluate_report(request: EvaluateReportRequest):
    """Evaluate report quality using automated metrics and optionally LLM-as-Judge."""
    try:
        evaluator = ReportEvaluator(use_llm=request.use_llm)

        if request.use_llm:
            result = await evaluator.evaluate(
                request.content, request.query, request.report_style or "default"
            )
            return EvaluateReportResponse(
                metrics=result.metrics.to_dict(),
                score=result.final_score,
                grade=result.grade,
                llm_evaluation=result.llm_evaluation.to_dict()
                if result.llm_evaluation
                else None,
                summary=result.summary,
            )
        else:
            result = evaluator.evaluate_metrics_only(
                request.content, request.report_style or "default"
            )
            return EvaluateReportResponse(
                metrics=result["metrics"],
                score=result["score"],
                grade=result["grade"],
            )
    except Exception as e:
        logger.exception(f"Error occurred during report evaluation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/prompt/enhance")
async def enhance_prompt(request: EnhancePromptRequest):
    try:
        sanitized_prompt = request.prompt.replace("\r\n", "").replace("\n", "")
        logger.info(f"Enhancing prompt: {sanitized_prompt}")

        # Convert string report_style to ReportStyle enum
        report_style = None
        if request.report_style:
            try:
                # Handle both uppercase and lowercase input
                style_mapping = {
                    "ACADEMIC": ReportStyle.ACADEMIC,
                    "POPULAR_SCIENCE": ReportStyle.POPULAR_SCIENCE,
                    "NEWS": ReportStyle.NEWS,
                    "SOCIAL_MEDIA": ReportStyle.SOCIAL_MEDIA,
                    "STRATEGIC_INVESTMENT": ReportStyle.STRATEGIC_INVESTMENT,
                }
                report_style = style_mapping.get(
                    request.report_style.upper(), ReportStyle.ACADEMIC
                )
            except Exception:
                # If invalid style, default to ACADEMIC
                report_style = ReportStyle.ACADEMIC
        else:
            report_style = ReportStyle.ACADEMIC

        workflow = build_prompt_enhancer_graph()
        final_state = workflow.invoke(
            {
                "prompt": request.prompt,
                "context": request.context,
                "report_style": report_style,
            }
        )
        return {"result": final_state["output"]}
    except Exception as e:
        logger.exception(f"Error occurred during prompt enhancement: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/mcp/server/metadata", response_model=MCPServerMetadataResponse)
async def mcp_server_metadata(request: MCPServerMetadataRequest):
    """Get information about an MCP server."""
    # Check if MCP server configuration is enabled
    if not get_bool_env("ENABLE_MCP_SERVER_CONFIGURATION", False):
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is disabled. Set ENABLE_MCP_SERVER_CONFIGURATION=true to enable MCP features.",
        )

    try:
        # Set default timeout for this endpoint (configurable via env)
        timeout = get_int_env("MCP_DEFAULT_TIMEOUT_SECONDS", 60)

        # Use custom timeout from request if provided
        if request.timeout_seconds is not None:
            timeout = request.timeout_seconds

        # Get sse_read_timeout from request if provided
        sse_read_timeout = request.sse_read_timeout

        # Load tools from the MCP server using the utility function
        tools = await load_mcp_tools(
            server_type=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            timeout_seconds=timeout,
            sse_read_timeout=sse_read_timeout,
        )

        # Create the response with tools
        response = MCPServerMetadataResponse(
            transport=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            tools=tools,
        )

        return response
    except Exception as e:
        logger.exception(f"Error in MCP server metadata endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.get("/api/rag/config", response_model=RAGConfigResponse)
async def rag_config():
    """Get the config of the RAG."""
    return RAGConfigResponse(provider=SELECTED_RAG_PROVIDER)


@app.get("/api/rag/resources", response_model=RAGResourcesResponse)
async def rag_resources(request: Annotated[RAGResourceRequest, Query()]):
    """Get the resources of the RAG."""
    retriever = build_retriever()
    if retriever:
        return RAGResourcesResponse(resources=retriever.list_resources(request.query))
    return RAGResourcesResponse(resources=[])


MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".md", ".txt"}


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks."""
    # Extract only the base filename, removing any path components
    basename = os.path.basename(filename)
    # Remove any null bytes or other dangerous characters
    sanitized = basename.replace("\x00", "").strip()
    # Ensure filename is not empty after sanitization
    if not sanitized or sanitized in (".", ".."):
        return "unnamed_file"
    return sanitized


@app.post("/api/rag/upload", response_model=Resource)
async def upload_rag_resource(file: UploadFile):
    # Validate filename exists
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required for upload")

    # Sanitize filename to prevent path traversal
    safe_filename = _sanitize_filename(file.filename)

    # Validate file extension
    _, ext = os.path.splitext(safe_filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Only {', '.join(ALLOWED_EXTENSIONS)} files are allowed.",
        )

    # Read content with size limit check
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Cannot upload an empty file")
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    retriever = build_retriever()
    if not retriever:
        raise HTTPException(status_code=500, detail="RAG provider not configured")
    try:
        return retriever.ingest_file(content, safe_filename)
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Upload not supported by current RAG provider"
        )
    except ValueError as exc:
        # Invalid user input or unsupported file content; treat as a client error
        logger.warning("Invalid RAG resource upload: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Invalid RAG resource. Please check the file and try again.",
        )
    except RuntimeError as exc:
        # Internal error during ingestion; log and return a generic server error
        logger.exception("Runtime error while ingesting RAG resource: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to ingest RAG resource due to an internal error.",
        )


@app.get("/api/config", response_model=ConfigResponse)
async def config():
    """Get the config of the server."""
    return ConfigResponse(
        rag=RAGConfigResponse(provider=SELECTED_RAG_PROVIDER),
        models=get_configured_llm_models(),
    )
