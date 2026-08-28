# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT


from dataclasses import field
from typing import Any

from langgraph.graph import MessagesState

from src.prompts.planner_model import Plan
from src.rag import Resource


class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""

    # Runtime Variables
    locale: str = "en-US"
    research_topic: str = ""
    clarified_research_topic: str = (
        ""  # Complete/final clarified topic with all clarification rounds
    )
    observations: list[str] = []
    resources: list[Resource] = []
    plan_iterations: int = 0
    current_plan: Plan | str = None
    final_report: str = ""
    # Offline e-commerce MVP fields. The default research workflow does not
    # populate these fields; the dedicated e-commerce graph does.
    ecommerce_request: dict[str, Any] = field(default_factory=dict)
    ecommerce_report: dict[str, Any] = field(default_factory=dict)
    ecommerce_report_fingerprint: str = ""
    ecommerce_metrics: dict[str, Any] = field(default_factory=dict)
    ecommerce_search_config: dict[str, Any] = field(default_factory=dict)
    ecommerce_model_config: dict[str, Any] = field(default_factory=dict)
    ecommerce_data_config: dict[str, Any] = field(default_factory=dict)
    ecommerce_model_status: str = "not_used"
    ecommerce_model_error_kind: str | None = None
    ecommerce_model_usage: dict[str, Any] = field(default_factory=dict)
    ecommerce_search_status: str = "not_used"
    ecommerce_search_details: dict[str, Any] = field(default_factory=dict)
    ecommerce_knowledge_config: dict[str, Any] = field(default_factory=dict)
    ecommerce_knowledge_status: str = "not_used"
    ecommerce_knowledge_details: dict[str, Any] = field(default_factory=dict)
    ecommerce_agent_plan: list[str] = field(default_factory=list)
    ecommerce_agent_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    ecommerce_progress_events: list[dict[str, Any]] = field(default_factory=list)
    ecommerce_provenance: list[dict[str, Any]] = field(default_factory=list)
    ecommerce_citation_validation: dict[str, Any] = field(default_factory=dict)
    ecommerce_verification_records: list[dict[str, Any]] = field(default_factory=list)
    ecommerce_verification_validation: dict[str, Any] = field(default_factory=dict)
    auto_accepted_plan: bool = False
    enable_background_investigation: bool = True
    background_investigation_results: str = None

    # Citation metadata collected during research
    # Format: List of citation dictionaries with url, title, description, etc.
    citations: list[dict[str, Any]] = field(default_factory=list)

    # Clarification state tracking (disabled by default)
    enable_clarification: bool = (
        False  # Enable/disable clarification feature (default: False)
    )
    clarification_rounds: int = 0
    clarification_history: list[str] = field(default_factory=list)
    is_clarification_complete: bool = False
    max_clarification_rounds: int = (
        3  # Default: 3 rounds (only used when enable_clarification=True)
    )

    # Workflow control
    goto: str = "planner"  # Default next node
