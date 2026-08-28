"""Optional real-model enhancement for the deterministic e-commerce report."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from pydantic import BaseModel, Field

from .models import FinalReport


class LLMReportDraft(BaseModel):
    """Small structured payload that the model is allowed to rewrite."""

    executive_summary: str = Field(min_length=1, max_length=1200)
    recommendations: list["LLMRecommendationDraft"] = Field(min_length=1, max_length=20)


class LLMRecommendationDraft(BaseModel):
    """Language-only edits for one recommendation, kept in report order."""

    positioning: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=800)


@dataclass(frozen=True)
class ModelUsage:
    """Provider usage normalized across LangChain response shapes."""

    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    available: bool = False
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "usage_available": self.available,
            "usage_source": self.source,
        }


class DeepSeekReportEnhancer:
    """Use the configured DeerFlow basic model to polish a verified report.

    Scores, evidence, prices and warnings stay deterministic and are never
    replaced by model-generated values. This makes the real-model path useful
    for language quality while preserving traceability and safe fallback.
    """

    def __init__(self, llm: Any = None):
        if llm is None:
            from src.llms.llm import get_llm_by_type

            llm = get_llm_by_type("basic")
        self.llm = llm
        self.usage = ModelUsage()

    def enhance(self, report: FinalReport) -> FinalReport:
        if not report.recommendations:
            return report

        try:
            structured_llm = self.llm.with_structured_output(
                LLMReportDraft,
                method="json_mode",
                include_raw=True,
            )
        except TypeError:
            try:
                structured_llm = self.llm.with_structured_output(LLMReportDraft, method="json_mode")
            except TypeError:
                # Keep compatibility with small test doubles and custom providers
                # that implement the older one-argument method.
                structured_llm = self.llm.with_structured_output(LLMReportDraft)
        response = structured_llm.invoke(self._messages(report))
        raw_response = response.get("raw") if isinstance(response, dict) else None
        parsed_response = response.get("parsed") if isinstance(response, dict) else response
        parsing_error = response.get("parsing_error") if isinstance(response, dict) else None
        if parsed_response is None and parsing_error is not None:
            raise parsing_error
        self.usage = self._extract_usage(raw_response)
        if not self.usage.model:
            self.usage = replace(self.usage, model=str(getattr(self.llm, "model_name", "")))
        draft = (
            parsed_response
            if isinstance(parsed_response, LLMReportDraft)
            else LLMReportDraft.model_validate(parsed_response)
        )
        if len(draft.recommendations) != len(report.recommendations):
            raise ValueError("structured recommendation count does not match the report")
        recommendations = [
            item.model_copy(
                update={
                    "positioning": draft_item.positioning,
                    "rationale": draft_item.rationale,
                }
            )
            for item, draft_item in zip(report.recommendations, draft.recommendations, strict=True)
        ]
        return report.model_copy(
            update={
                "executive_summary": draft.executive_summary,
                "recommendations": recommendations,
            }
        )

    @staticmethod
    def _messages(report: FinalReport) -> list[tuple[str, str]]:
        payload = report.model_dump(mode="json")
        return [
            (
                "system",
                "你是电商选品报告编辑。只能根据给定报告改写表达，不得新增未被证据支持的事实、价格、销量、趋势或引用。必须保留‘只能先验证、不能直接采购/放量’的决策边界，并让每个方向的定位和验证动作保持不同。输出必须是 JSON，并且只包含结构化字段。",
            ),
            (
                "user",
                "请将下面的选品报告改写成简洁、可执行的中文摘要。摘要必须点出首选验证方向、第一步验证动作和当前不能直接放量的原因。保留评分、证据和风险的含义；只返回 JSON 对象中的 executive_summary 和 recommendations。recommendations 必须与原报告推荐方向数量相同、顺序一致，每项只包含 positioning 和 rationale，不能合并或复制不同推荐方向的定位。\n\n"
                + json.dumps(payload, ensure_ascii=False),
            ),
        ]

    @staticmethod
    def _extract_usage(raw_response: Any) -> ModelUsage:
        if raw_response is None:
            return ModelUsage()
        if isinstance(raw_response, dict):
            usage = raw_response.get("usage_metadata") or {}
            metadata = raw_response.get("response_metadata") or {}
        else:
            usage = getattr(raw_response, "usage_metadata", None) or {}
            metadata = getattr(raw_response, "response_metadata", None) or {}
        provider_usage = metadata.get("token_usage") or metadata.get("usage") or {}
        usage_source = ""
        if usage:
            usage_source = "usage_metadata"
        elif provider_usage:
            usage_source = "response_metadata.token_usage"
        input_tokens = usage.get("input_tokens") or provider_usage.get("prompt_tokens") or 0
        output_tokens = usage.get("output_tokens") or provider_usage.get("completion_tokens") or 0
        total_tokens = usage.get("total_tokens") or provider_usage.get("total_tokens") or input_tokens + output_tokens
        model = metadata.get("model_name") or metadata.get("model") or ""
        return ModelUsage(
            model=str(model),
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            total_tokens=int(total_tokens),
            available=bool(usage or provider_usage),
            source=usage_source,
        )
