"""Pure orchestration for the offline e-commerce research workflow."""

from __future__ import annotations

from collections.abc import Mapping
from statistics import median
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from .category_profiles import get_category_profile

from .models import (
    CompetitorInsight,
    CustomerProfile,
    EcommerceResearchRequest,
    Evidence,
    FinalReport,
    OpportunityRisk,
    ProductRecommendation,
    ProductScore,
    ResearchProgressEvent,
    TrendSignal,
)
from .providers import MockResearchProvider, ResearchProvider


class ResearchResult(BaseModel):
    """Dual-format result suitable for a CLI or a future graph state field."""

    report: FinalReport
    markdown: str
    warnings: list[str] = Field(default_factory=list)
    research_mode: str = "Mock"
    model_status: Literal["not_used", "success", "fallback"] = "not_used"
    model_error_kind: str | None = None
    model_usage: dict[str, Any] = Field(default_factory=dict)
    search_status: str = "not_used"
    search_details: dict[str, Any] = Field(default_factory=dict)
    progress_events: list[ResearchProgressEvent] = Field(default_factory=list)
    agent_plan: list[str] = Field(default_factory=list)
    agent_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
    knowledge_status: str = "not_used"
    knowledge_details: dict[str, Any] = Field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        """Return only standard JSON-compatible values."""

        return self.model_dump(mode="json")


class ReportEnhancer(Protocol):
    """Optional post-processor for a fully structured report."""

    def enhance(self, report: FinalReport) -> FinalReport: ...


class MarketResearch:
    def __init__(self, provider: ResearchProvider):
        self.provider = provider

    def run(self, request: EcommerceResearchRequest) -> tuple[list[TrendSignal], list[Evidence]]:
        return self.provider.market_research(request)


class CompetitorResearch:
    def __init__(self, provider: ResearchProvider):
        self.provider = provider

    def run(self, request: EcommerceResearchRequest) -> tuple[list[CompetitorInsight], list[Evidence]]:
        return self.provider.competitor_research(request)


class CustomerResearch:
    def __init__(self, provider: ResearchProvider):
        self.provider = provider

    def run(self, request: EcommerceResearchRequest) -> tuple[list[CustomerProfile], list[Evidence]]:
        return self.provider.customer_research(request)


class OpportunityRiskAnalysis:
    def __init__(self, provider: ResearchProvider):
        self.provider = provider

    def run(self, request: EcommerceResearchRequest) -> tuple[list[OpportunityRisk], list[Evidence]]:
        return self.provider.opportunity_risk(request)


def _score(
    trends: list[TrendSignal],
    competitors: list[CompetitorInsight],
    opportunities: list[OpportunityRisk],
    evidence: list[Evidence],
) -> ProductScore:
    demand = trends[0].demand_score if trends else 45.0
    opportunity = opportunities[0] if opportunities else None
    differentiation = opportunity.opportunity_score if opportunity else 45.0
    risk = opportunity.risk_score if opportunity else 60.0
    competition = max(25.0, 86.0 - len(competitors) * 12.0)
    margin = 62.0 if opportunity else 45.0
    evidence_quality = min(100.0, len(evidence) * 25.0)
    total = (
        demand * 0.30
        + competition * 0.18
        + margin * 0.18
        + differentiation * 0.20
        + (100.0 - risk) * 0.08
        + evidence_quality * 0.06
    )
    return ProductScore(
        demand=round(demand, 2),
        competition=round(competition, 2),
        margin=round(margin, 2),
        differentiation=round(differentiation, 2),
        evidence_quality=round(evidence_quality, 2),
        total=round(max(0.0, min(100.0, total)), 2),
    )


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _variant_score(score: ProductScore, adjustment: float) -> ProductScore:
    """Apply a visible direction hypothesis without pretending it is new evidence."""

    if not adjustment:
        return score
    return score.model_copy(
        update={
            "differentiation": _bounded(score.differentiation + adjustment),
            "margin": _bounded(score.margin + adjustment * 0.6),
            "total": _bounded(score.total + adjustment),
        }
    )


def _price_plan(
    request: EcommerceResearchRequest,
    competitors: list[CompetitorInsight],
    *,
    multiplier: float,
    width: float,
) -> tuple[str, str]:
    """Build a focused candidate price band from explicit competitor anchors.

    The request range is a research filter, not automatically a recommended
    retail band. When competitors do not contain explicit prices, the fallback
    is deliberately marked as an assumption so users do not mistake it for
    observed market data.
    """

    explicit_prices = [
        item.price
        for item in competitors
        if item.price > 0 and item.price_source not in {"request_midpoint", "mock_fixture"}
    ]
    if not explicit_prices:
        # Mock fixtures are still useful for deterministic UI behavior, but
        # should be labeled as assumptions rather than commercial evidence.
        explicit_prices = [
            item.price for item in competitors if item.price > 0 and item.price_source == "mock_fixture"
        ]
    if explicit_prices:
        anchor = float(median(explicit_prices))
        mock_only = all(
            item.price_source == "mock_fixture"
            for item in competitors
            if item.price > 0 and item.price_source != "request_midpoint"
        )
        source_label = "Mock 竞品价格锚点" if mock_only else "搜索结果中的竞品价格锚点"
        basis = (
            f"基于 {len(explicit_prices)} 个{source_label}的中位数 ¥{anchor:.0f}；"
            "仅用于形成候选价格假设，仍需核验成本、促销和平台扣点。"
        )
    else:
        anchor = (request.price_min + request.price_max) / 2
        basis = (
            f"未提取到明确竞品价格，暂以输入区间中点 ¥{anchor:.0f} 估算；"
            "该价格带不能用于采购或放量决策。"
        )
    center = max(0.0, anchor * multiplier)
    step = 50.0 if center >= 500 else 10.0
    low = max(step, round(center * (1 - width) / step) * step)
    high = max(low + step, round(center * (1 + width) / step) * step)
    return f"¥{low:.0f}-¥{high:.0f}", basis


class ReportGenerator:
    def generate(
        self,
        request: EcommerceResearchRequest,
        trends: list[TrendSignal],
        competitors: list[CompetitorInsight],
        customers: list[CustomerProfile],
        opportunities: list[OpportunityRisk],
        evidence: list[Evidence],
        warnings: list[str],
        research_mode: str = "Mock",
    ) -> FinalReport:
        score = _score(trends, competitors, opportunities, evidence)
        opportunity = opportunities[0] if opportunities else None
        customer = customers[0] if customers else None
        positioning = (
            opportunity.opportunity
            if opportunity
            else f"围绕{request.category}进行小规模验证，优先补充市场与竞品证据"
        )
        rationale = (
            opportunity.rationale
            if opportunity
            else "研究模块部分不可用，当前建议仅作为待验证假设。"
        )
        evidence_ids = [item.evidence_id for item in evidence]
        profile = get_category_profile(request.category)
        variants = profile.variants
        recommendations = [
            ProductRecommendation(
                product_name=f"{request.category}{variant.suffix}",
                positioning=variant.positioning,
                target_customer=(customer.segment if customer else request.target_customer),
                price_range="待计算",
                rationale=f"{rationale} {variant.rationale}",
                score=_variant_score(score, variant.score_adjustment),
                evidence_ids=evidence_ids,
                validation_action=variant.validation_action,
                validation_threshold=variant.validation_threshold,
                validation_data_needed=list(variant.validation_data_needed),
                validation_failure_action=variant.validation_failure_action,
                score_note=(
                    f"方向假设相对修正 {variant.score_adjustment:+.1f} 分；"
                    "不是新增市场证据。"
                ),
            )
            for variant in variants[: request.top_n]
        ]
        for recommendation, variant in zip(recommendations, variants, strict=False):
            recommendation.price_range, recommendation.price_basis = _price_plan(
                request,
                competitors,
                multiplier=variant.price_multiplier,
                width=variant.price_band_width,
            )
        first_recommendation = recommendations[0] if recommendations else None
        decision_status = "validate_first" if recommendations else "insufficient_evidence"
        decision_basis = (
            "当前报告缺少真实销量、单位成本、平台扣点、转化率、退款率和合规数据，"
            "只能用于确定验证优先级，不能直接据此采购或放量。"
        )
        next_actions = [
            f"优先验证：{first_recommendation.validation_action}"
            if first_recommendation
            else "补充至少一个可核验的竞品或商品来源",
            "补齐 3 个候选 SKU 的售价、销量周期、单位成本、库存和合规状态",
            "以 7-14 天小批量测试的转化率、退款率和毛利率作为是否继续投入的门槛",
        ]
        summary = (
            f"{request.category}在{request.target_market}的 {research_mode} 研究建议先验证"
            f"“{first_recommendation.product_name if first_recommendation else positioning}”。"
            f"当前最高方向评分为 {first_recommendation.score.total if first_recommendation else score.total:.1f}/100，"
            f"结果基于 {len(evidence)} 条结构化证据；本报告只给出验证优先级，不支持直接采购。"
        )
        return FinalReport(
            request=request,
            executive_summary=summary,
            recommendations=recommendations,
            trends=trends,
            competitors=competitors,
            customer_profiles=customers,
            opportunities_risks=opportunities,
            evidence=evidence,
            warnings=warnings,
            decision_status=decision_status,
            decision_basis=decision_basis,
            next_actions=next_actions,
        )


class Reviewer:
    """Check report completeness and add actionable degradation warnings."""

    def review(self, report: FinalReport) -> list[str]:
        warnings: list[str] = []
        if len(report.evidence) < 3:
            warnings.append("证据不足：当前结论仅适合生成选品假设，不应直接放量。")
        if not report.trends:
            warnings.append("市场趋势模块无结果，需求评分使用了保守默认值。")
        if not report.competitors:
            warnings.append("竞品模块无结果，竞争评分使用了保守默认值。")
        if not report.customer_profiles:
            warnings.append("用户画像模块无结果，目标客群沿用了输入描述。")
        if not report.opportunities_risks:
            warnings.append("机会风险模块无结果，建议先补充风险验证。")
        return warnings


def _request_from_input(request: EcommerceResearchRequest | Mapping[str, Any] | str | None) -> EcommerceResearchRequest:
    if request is None:
        return EcommerceResearchRequest()
    if isinstance(request, str):
        return EcommerceResearchRequest(category=request)
    if isinstance(request, Mapping):
        return EcommerceResearchRequest.model_validate(dict(request))
    return request


def _append_unique(items: list[str], values: list[str]) -> None:
    for value in values:
        if value and value not in items:
            items.append(value)


def _append_evidence_unique(items: list[Evidence], values: list[Evidence]) -> None:
    """Merge repeated canonical search evidence while preserving module tags."""

    by_id = {item.evidence_id: item for item in items}
    for value in values:
        existing = by_id.get(value.evidence_id)
        if existing is None:
            items.append(value)
            by_id[value.evidence_id] = value
            continue
        existing.confidence = max(existing.confidence, value.confidence)
        _append_unique(existing.supports, value.supports)


def _progress_events(
    *,
    search_status: str,
    search_details: Mapping[str, Any],
    evidence: list[Evidence],
    recommendations: list[ProductRecommendation],
    model_status: str,
) -> list[ResearchProgressEvent]:
    """Convert provider/module telemetry into one stable progress timeline."""

    events = [
        ResearchProgressEvent(
            event_id="request-validated",
            stage="request",
            status="success",
            message="研究参数已校验，开始执行研究流程。",
        )
    ]
    module_labels = {
        "market": "市场趋势",
        "competitor": "竞品分析",
        "customer": "用户画像",
        "opportunity": "机会风险",
    }
    for module, label in module_labels.items():
        details = dict(search_details.get(module, {}))
        module_status = str(details.get("status", "success" if not search_details else "unknown"))
        event_status = (
            "success" if module_status == "success" or not search_details
            else "partial" if module_status == "fallback"
            else "error"
        )
        events.append(
            ResearchProgressEvent(
                event_id=f"search-{module}",
                stage="search",
                status=event_status,
                module=module,
                message=(
                    f"{label}搜索完成。"
                    if event_status == "success"
                    else f"{label}搜索未完全成功，已保留降级结果。"
                ),
                metrics={
                    "result_count": int(details.get("result_count", 0) or 0),
                    "priced_result_count": int(details.get("priced_result_count", 0) or 0),
                    "status": module_status,
                },
            )
        )
        events.append(
            ResearchProgressEvent(
                event_id=f"clean-{module}",
                stage="clean",
                status=event_status,
                module=module,
                message=f"{label}结果已清洗并完成来源质量标记。",
                metrics={
                    "cleaned_result_count": int(details.get("cleaned_result_count", details.get("result_count", 0)) or 0),
                    "cleaned_duplicate_count": int(details.get("cleaned_duplicate_count", 0) or 0),
                    "quality_warning_count": len(details.get("quality_warnings", []) or []),
                },
            )
        )
    events.extend(
        [
            ResearchProgressEvent(
                event_id="score-completed",
                stage="score",
                status="success" if recommendations else "error",
                message="推荐方向已完成可解释评分。" if recommendations else "没有生成可评分的推荐方向。",
                metrics={
                    "recommendation_count": len(recommendations),
                    "evidence_count": len(evidence),
                },
            ),
            ResearchProgressEvent(
                event_id="report-completed",
                stage="report",
                status="success" if recommendations else "partial",
                message="验证型研究报告已生成。" if recommendations else "报告已生成，但证据不足。",
                metrics={
                    "recommendation_count": len(recommendations),
                    "model_status": model_status,
                },
            ),
            ResearchProgressEvent(
                event_id="run-completed",
                stage="complete",
                status="partial" if search_status in {"partial", "fallback"} or model_status == "fallback" else "success",
                message="研究完成；请先按验证卡片补齐商业数据。",
                metrics={"search_status": search_status, "model_status": model_status},
            ),
        ]
    )
    return events


def classify_model_error(error: Exception) -> str:
    """Map model exceptions to stable, non-sensitive operational labels."""

    name = type(error).__name__.lower()
    message = str(error).lower()
    if (
        isinstance(error, UnicodeError)
        or any(token in name for token in ("unicode", "encoding", "decode", "encode"))
        or any(token in message for token in ("ascii codec", "utf-8 codec", "codec can't"))
    ):
        return "encoding_error"
    if any(code in message for code in ("401", "403", "unauthorized", "forbidden", "invalid api key")):
        return "auth_error"
    if "429" in message or "rate limit" in message or "too many requests" in message:
        return "rate_limit"
    if "timeout" in name or "timeout" in message:
        return "timeout"
    if any(token in name for token in ("connect", "network", "remoteprotocol", "readerror")) or any(
        token in message for token in ("connection error", "connection refused", "dns")
    ):
        return "network_error"
    if any(token in name for token in ("validation", "parser", "parse")) or any(
        token in message for token in ("structured output", "validation error", "could not parse")
    ):
        return "response_parse_error"
    if any(token in name for token in ("apierror", "badrequest", "httpstatus", "openaierror")) or any(
        token in message for token in ("http 400", "http 422", "http 500", "http 502", "http 503")
    ):
        return "provider_error"
    if "api key" in message or (
        "model" in message
        and any(token in message for token in ("not found", "does not exist", "missing", "配置"))
    ):
        return "config_error"
    return "unknown_error"


_PRICE_SOURCE_LABELS = {
    "explicit": "显式价格",
    "request_midpoint": "请求区间中点占位",
    "mock_fixture": "Mock 固定样本",
}


def _red_blue_judgment(report: FinalReport) -> str:
    """Heuristic red/blue-ocean label, always marked as non-measured."""

    score = report.recommendations[0].score.competition if report.recommendations else None
    count = len(report.competitors)
    if score is None:
        return "- 红海/蓝海判断：暂无竞争评分，无法形成判断；请补充竞品证据。"
    if score >= 70:
        label = "偏蓝海"
    elif score >= 40:
        label = "竞争中性"
    else:
        label = "偏红海"
    return (
        f"- 红海/蓝海判断（启发式，非市场实测）：{label}。"
        f"依据：竞争评分 {score:.1f}/100、可比较竞品 {count} 个；"
        "该判断仅基于当前结构化证据，需平台销量榜单与份额数据验证。"
    )


def price_band_analysis_lines(report: FinalReport) -> list[str]:
    """Standalone price-band analysis: anchors, mainstream band, gap hypothesis."""

    anchors = [
        item
        for item in report.competitors
        if item.price > 0 and item.price_source != "request_midpoint"
    ]
    if not anchors:
        return ["- 暂无可用价格锚点；价格带分析需补充竞品价格证据。"]
    lines = [
        f"- {item.name}：¥{item.price:.0f}（{_PRICE_SOURCE_LABELS.get(item.price_source, item.price_source)}）"
        for item in anchors
    ]
    prices = sorted(item.price for item in anchors)
    anchor = float(median(prices))
    mock_only = all(item.price_source == "mock_fixture" for item in anchors)
    anchor_label = "Mock 锚点" if mock_only else "竞品锚点"
    lines.append(
        f"- 主流价格区间：¥{prices[0]:.0f} ~ ¥{prices[-1]:.0f}，"
        f"{anchor_label}中位数 ¥{anchor:.0f}（{len(prices)} 个锚点）。"
    )
    if mock_only:
        lines.append("- 注意：当前价格锚点全部来自 Mock 固定样本，仅用于演示流程，不代表真实市场价格。")
    bands = [item.price_range for item in report.recommendations if item.price_range and item.price_range != "待计算"]
    if bands:
        lines.append(f"- 候选推荐价格带：{'、'.join(dict.fromkeys(bands))}（依据见推荐方向的价格依据）。")
    # Gap hypothesis: widest uncovered interval inside the request range.
    # Require at least 3 anchors; with fewer, any "gap" is an artifact of
    # sparse sampling rather than market whitespace.
    if len(prices) < 3:
        lines.append(
            f"- 空白价格带：锚点不足（当前 {len(prices)} 个，至少需 3 个），"
            "不做空白区间推断；请补充竞品价格证据。"
        )
        return lines
    points = [report.request.price_min, *prices, report.request.price_max]
    points = sorted({float(p) for p in points if p > 0})
    min_width = max(20.0, anchor * 0.15)
    gaps = [
        (high - low, low, high)
        for low, high in zip(points, points[1:], strict=False)
        if high - low >= min_width
    ]
    if gaps:
        width, low, high = max(gaps)
        lines.append(
            f"- 空白价格带候选（假设，需验证）：¥{low:.0f} ~ ¥{high:.0f}（宽度 ¥{width:.0f}）。"
            "该区间内部当前无竞品锚点，可能是机会也可能是无需求区，需小批量测试验证。"
        )
    else:
        lines.append("- 空白价格带：基于当前锚点未发现明显未覆盖区间；锚点密度不足时该结论不可靠。")
    return lines


def _render_markdown(
    report: FinalReport,
    *,
    model_status: Literal["not_used", "success", "fallback"] = "not_used",
    model_error_kind: str | None = None,
    search_status: str = "not_used",
) -> str:
    status_labels = {
        "not_used": "未使用真实模型",
        "success": "DeepSeek 调用成功",
        "fallback": "DeepSeek 调用失败，已降级",
    }
    search_labels = {
        "not_used": "未使用真实搜索",
        "success": "真实搜索成功",
        "partial": "真实搜索部分失败，混合 Mock",
        "fallback": "真实搜索失败，已回退 Mock",
    }
    model_line = f"**模型状态**：{status_labels[model_status]}"
    if model_error_kind:
        model_line += f"（{model_error_kind}）"
    lines = [
        f"# 电商选品研究报告：{report.request.category}",
        "",
        model_line,
        f"**数据状态**：{search_labels.get(search_status, search_status)}",
        f"**研究市场**：{report.request.target_market}  ",
        f"**目标客群**：{report.request.target_customer}",
        "",
        "## 结论摘要",
        "",
        report.executive_summary,
        "",
        "## 执行决策",
        "",
        f"- 当前状态：{report.decision_status}",
        f"- 判断依据：{report.decision_basis}",
        "- 下一步动作：",
        *[f"  1. {action}" for action in report.next_actions],
        "",
        "## 一、市场概况",
        "",
    ]
    if report.trends:
        lines.extend(
            f"- {item.name}：{item.direction}，需求 {item.demand_score:.1f}/100，"
            f"增速 {item.growth_rate * 100:.0f}%（证据 {', '.join(item.evidence_ids)}）"
            for item in report.trends
        )
    else:
        lines.append("- 暂无可用趋势信号；请补充搜索或商品数据。")
    lines.append("- 品类规模与季节性：当前数据源不含市场规模绝对值与全年季节性指数，已列入待补证据；增速仅为所引用趋势的相对信号。")
    lines.append("")

    lines.extend(["## 二、竞争格局", ""])
    if report.competitors:
        lines.extend(
            f"- {item.name}：¥{item.price:.0f}（{_PRICE_SOURCE_LABELS.get(item.price_source, item.price_source)}），"
            f"{item.positioning}；卖点 {'、'.join(item.strengths) or '未提取'}；"
            f"短板 {'、'.join(item.weaknesses) or '未提取'}（证据 {', '.join(item.evidence_ids)}）"
            for item in report.competitors
        )
    else:
        lines.append("- 暂无可比较竞品；竞争结论不能直接用于进入决策。")
    lines.append("- 头部集中度：当前数据源不含平台销量榜单，无法计算 CR5/CR10，已列入待补证据。")
    lines.append(_red_blue_judgment(report))
    lines.append("")

    lines.extend(["## 三、价格带分析", ""])
    lines.extend(price_band_analysis_lines(report))
    lines.append("")

    lines.extend(["## 四、目标人群匹配", ""])
    if report.customer_profiles:
        for item in report.customer_profiles:
            lines.append(f"- {item.segment}：需求 {'、'.join(item.needs)}；痛点 {'、'.join(item.pain_points)}；购买触发 {'、'.join(item.buying_triggers)}（证据 {', '.join(item.evidence_ids)}）")
        first_segment = report.customer_profiles[0].segment
        lines.append(f"- 品类契合点：{report.request.category}与「{first_segment}」的匹配基于上述需求与痛点的交集；该判断为结构化推断，需真实用户访谈或评论数据验证。")
    else:
        lines.append("- 暂无可用客群画像；请补充目标用户访谈或商品数据。")
    lines.append("")

    lines.extend(["## 五、风险与进入壁垒", ""])
    if report.opportunities_risks:
        for item in report.opportunities_risks:
            lines.append(f"- 机会 {item.opportunity_score:.1f}/100：{item.opportunity}")
            lines.append(f"  - 依据：{item.rationale}")
            lines.append(f"  - 风险 {item.risk_score:.1f}/100：{'；'.join(item.risks)}")
            lines.append(f"  - 缓解：{'；'.join(item.mitigations)}（证据 {', '.join(item.evidence_ids)}）")
    else:
        lines.append("- 暂无机会/风险评估；当前不能形成进入结论。")
    lines.append("- 进入壁垒细分：供应链门槛、资质要求、退货率风险暂无专项数据源；以上为机会风险模块的通用评估，专项数据已列入待补证据。")
    lines.append("")

    lines.extend(["## 六、推荐方向与验证动作", ""])
    if report.recommendations:
        for item in report.recommendations:
            lines.extend([
                f"### {item.product_name} — {item.score.total:.1f}/100",
                f"- 定位：{item.positioning}",
                f"- 价格带：{item.price_range}",
                f"- 适合客群：{item.target_customer}",
                f"- 理由：{item.rationale}",
                f"- 价格依据：{item.price_basis}",
                f"- 证据：{', '.join(item.evidence_ids) or '暂无'}",
                f"- 评分说明：{item.score_note}",
                f"- 建议验证：{item.validation_action}",
                f"- 成功阈值：{item.validation_threshold}",
                f"- 需要补齐：{'、'.join(item.validation_data_needed)}",
                f"- 未达标处理：{item.validation_failure_action}",
                "",
            ])
    else:
        lines.append("- 暂无推荐方向；请先补齐证据。")

    lines.extend(["## 证据详情", ""])
    if report.evidence:
        lines.extend(
            f"- [{item.evidence_id}] {item.title}：{item.summary}（置信度 {item.confidence:.2f}，来源 {item.source}）"
            for item in report.evidence
        )
    else:
        lines.append("- 暂无证据。")
    lines.append("")
    if report.warnings:
        lines.extend(["## Warnings", "", *[f"- {warning}" for warning in report.warnings], ""])
    return "\n".join(lines).rstrip() + "\n"


def run_mock_research(
    request: EcommerceResearchRequest | Mapping[str, Any] | str | None = None,
    provider: ResearchProvider | None = None,
) -> ResearchResult:
    """Run all research roles with the deterministic Mock provider."""

    return run_research(request, provider=provider, research_mode="Mock")


def run_deepseek_research(
    request: EcommerceResearchRequest | Mapping[str, Any] | str | None = None,
    provider: ResearchProvider | None = None,
    *,
    llm: Any = None,
) -> ResearchResult:
    """Run the MVP with configured DeepSeek report-language enhancement."""

    from .llm_report import DeepSeekReportEnhancer

    return run_research(
        request,
        provider=provider,
        research_mode="DeepSeek",
        report_enhancer=DeepSeekReportEnhancer(llm=llm),
    )


def run_research(
    request: EcommerceResearchRequest | Mapping[str, Any] | str | None = None,
    provider: ResearchProvider | None = None,
    *,
    research_mode: str = "Mock",
    report_enhancer: ReportEnhancer | None = None,
    knowledge_retriever: Any = None,
    knowledge_top_k: int = 3,
    use_agent_graph: bool = True,
) -> ResearchResult:
    """Run all research roles for any provider and degrade per module.

    ``use_agent_graph`` is an internal experiment switch.  The default keeps
    the V1 graph contract unchanged; the sequential branch gives A4 a real
    single-pipeline baseline without changing the public result schema.
    """

    request_model = _request_from_input(request)
    active_provider = provider or MockResearchProvider()
    knowledge_status = "not_used"
    knowledge_details: dict[str, Any] = {}
    if knowledge_retriever is not None:
        from .knowledge.integration import KnowledgeAugmentedProvider

        active_provider = KnowledgeAugmentedProvider(
            active_provider,
            knowledge_retriever,
            top_k=knowledge_top_k,
        )
    model_status: Literal["not_used", "success", "fallback"] = "not_used"
    model_error_kind: str | None = None
    prepare_parallel = getattr(active_provider, "prepare_parallel", None)
    if callable(prepare_parallel):
        prepare_parallel(request_model)

    if use_agent_graph:
        # Keep the public ResearchResult stable while moving the internal
        # execution boundary to an explicit, inspectable agent graph.
        from .agent_graph import run_ecommerce_agent_graph

        agent_state = run_ecommerce_agent_graph(
            request_model,
            provider=active_provider,
            research_mode=research_mode,
        )
    else:
        agent_state = _run_sequential_research(
            request_model,
            provider=active_provider,
            research_mode=research_mode,
        )
    warnings = list(agent_state.get("warnings") or [])
    _append_unique(warnings, list(getattr(active_provider, "knowledge_warnings", []) or []))
    evidence = [Evidence.model_validate(item) for item in agent_state.get("evidence", [])]
    report = FinalReport.model_validate(agent_state.get("report") or {})
    _append_unique(report.warnings, warnings)
    knowledge_status = str(getattr(active_provider, "knowledge_status", "not_used"))
    knowledge_details = dict(getattr(active_provider, "knowledge_details", {}) or {})
    search_status = str(getattr(active_provider, "search_status", "not_used"))
    search_details = dict(getattr(active_provider, "module_status", {}))
    if report_enhancer is not None:
        try:
            report = report_enhancer.enhance(report)
            model_status = "success"
        except Exception as exc:  # noqa: BLE001 - real-model failure must degrade safely
            model_status = "fallback"
            model_error_kind = classify_model_error(exc)
            _append_unique(
                warnings,
                [f"真实模型报告润色失败（{model_error_kind}），已保留结构化报告。"],
            )
            _append_unique(report.warnings, warnings)
    model_usage = {}
    if report_enhancer is not None:
        usage = getattr(report_enhancer, "usage", None)
        if usage is not None and hasattr(usage, "to_dict"):
            model_usage = usage.to_dict()
    if model_status == "fallback":
        report.executive_summary = report.executive_summary.replace(
            "DeepSeek 研究建议", "DeepSeek（降级）研究建议"
        )
    _append_unique(report.warnings, Reviewer().review(report))
    progress_events = _progress_events(
        search_status=search_status,
        search_details=search_details,
        evidence=evidence,
        recommendations=report.recommendations,
        model_status=model_status,
    )
    return ResearchResult(
        report=report,
        markdown=_render_markdown(
            report,
            model_status=model_status,
            model_error_kind=model_error_kind,
            search_status=search_status,
        ),
        warnings=report.warnings,
        research_mode=research_mode,
        model_status=model_status,
        model_error_kind=model_error_kind,
        model_usage=model_usage,
        search_status=search_status,
        search_details=search_details,
        progress_events=progress_events,
        agent_plan=list(agent_state.get("agent_plan") or []),
        agent_results=dict(agent_state.get("agent_results") or {}),
        knowledge_status=knowledge_status,
        knowledge_details=knowledge_details,
    )


def _run_sequential_research(
    request: EcommerceResearchRequest,
    *,
    provider: ResearchProvider,
    research_mode: str,
) -> dict[str, Any]:
    """Run the four provider workers in one legacy-style sequential pipeline.

    This path is intentionally kept private and is only used by A4 ablation
    experiments.  Each module still degrades independently, so its output is
    comparable with the agent graph while its execution metadata is visibly
    different.
    """

    warnings = list(getattr(provider, "warnings", []) or [])
    evidence: list[Evidence] = []
    outputs: dict[str, list[Any]] = {
        "trends": [],
        "competitors": [],
        "customers": [],
        "opportunities": [],
    }
    workers = (
        ("market", MarketResearch, "trends"),
        ("competitor", CompetitorResearch, "competitors"),
        ("customer", CustomerResearch, "customers"),
        ("opportunity", OpportunityRiskAnalysis, "opportunities"),
    )
    for module, worker_type, output_key in workers:
        try:
            values, new_evidence = worker_type(provider).run(request)
            outputs[output_key] = list(values)
            _append_evidence_unique(evidence, list(new_evidence))
        except Exception as exc:  # noqa: BLE001 - ablation path must degrade
            kind = classify_model_error(exc)
            _append_unique(warnings, [f"{module} 模块失败（{kind}），已跳过该模块。"])

    report = ReportGenerator().generate(
        request,
        outputs["trends"],
        outputs["competitors"],
        outputs["customers"],
        outputs["opportunities"],
        evidence,
        warnings,
        research_mode=research_mode,
    )
    return {
        "warnings": warnings,
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "report": report.model_dump(mode="json"),
        "agent_plan": [],
        "agent_results": {},
    }
