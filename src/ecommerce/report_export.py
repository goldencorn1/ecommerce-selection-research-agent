"""Small dependency-free report exporters for user-facing previews."""

from __future__ import annotations

from html import escape
from typing import Any

from .models import FinalReport
from .orchestration import price_band_analysis_lines


def _status_badge(label: str, value: str) -> str:
    return (
        f'<span class="badge"><strong>{escape(label)}</strong> '
        f'{escape(value)}</span>'
    )


def render_html_report(
    report: FinalReport | dict[str, Any],
    *,
    search_status: str = "unknown",
    model_status: str = "unknown",
) -> str:
    """Render a saved report as a standalone, dependency-free HTML document."""

    report_model = report if isinstance(report, FinalReport) else FinalReport.model_validate(report)
    request = report_model.request
    recommendations = "".join(
        "<tr>"
        f"<td>{escape(item.product_name)}</td>"
        f"<td>{escape(item.positioning)}<br><small>客群：{escape(item.target_customer)}</small></td>"
        f"<td><strong>{escape(item.price_range)}</strong><br><small>{escape(item.price_basis)}</small></td>"
        f"<td class=score>{item.score.total:.1f}<br><small>需求 {item.score.demand:.0f} / 竞争 {item.score.competition:.0f}<br>利润 {item.score.margin:.0f} / 差异 {item.score.differentiation:.0f}<br>证据 {item.score.evidence_quality:.0f}</small></td>"
        f"<td>{escape(item.rationale)}<hr><strong>验证卡片</strong><br>动作：{escape(item.validation_action)}<br>成功阈值：{escape(item.validation_threshold)}<br>需要补齐：{escape('、'.join(item.validation_data_needed))}<br>未达标处理：{escape(item.validation_failure_action)}<br><small>{escape(item.score_note)}</small></td>"
        "</tr>"
        for item in report_model.recommendations
    )
    evidence = "".join(
        "<tr>"
        f"<td>{escape(item.title)}</td>"
        f"<td>{escape(item.summary)}</td>"
        f"<td><a href=\"{escape(item.source, quote=True)}\" target=\"_blank\" rel=\"noreferrer\">打开来源</a></td>"
        f"<td>{item.confidence:.2f}</td>"
        f"<td>{escape(item.source_type)}</td>"
        "</tr>"
        for item in report_model.evidence
    )
    warnings = "".join(f"<li>{escape(item)}</li>" for item in report_model.warnings)
    warning_block = f"<ul class=warnings>{warnings}</ul>" if warnings else "<p>无运行告警。</p>"
    trend_rows = "".join(
        f"<li><strong>{escape(item.name)}</strong>：{escape(item.direction)}，需求 {item.demand_score:.1f}/100；证据 {escape(', '.join(item.evidence_ids) or '暂无')}</li>"
        for item in report_model.trends
    ) or "<li>暂无可用趋势信号。</li>"
    competitor_rows = "".join(
        f"<li><strong>{escape(item.name)}</strong>：¥{item.price:.0f}，{escape(item.positioning)}；证据 {escape(', '.join(item.evidence_ids) or '暂无')}</li>"
        for item in report_model.competitors
    ) or "<li>暂无可比较竞品。</li>"
    customer_rows = "".join(
        f"<li><strong>{escape(item.segment)}</strong>：需求 {escape('、'.join(item.needs))}；痛点 {escape('、'.join(item.pain_points))}；触发 {escape('、'.join(item.buying_triggers))}</li>"
        for item in report_model.customer_profiles
    ) or "<li>暂无可用客群画像。</li>"
    risk_rows = "".join(
        f"<li><strong>机会 {item.opportunity_score:.1f}</strong>：{escape(item.opportunity)}；风险 {item.risk_score:.1f}：{escape('；'.join(item.risks))}；缓解 {escape('；'.join(item.mitigations))}</li>"
        for item in report_model.opportunities_risks
    ) or "<li>暂无机会/风险评估。</li>"
    price_band_rows = "".join(
        f"<li>{escape(line.removeprefix('- '))}</li>"
        for line in price_band_analysis_lines(report_model)
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>电商选品报告：{escape(request.category)}</title>
  <style>
    :root {{ color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f5f7fb; color: #1f2937; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1 {{ margin-bottom: 8px; }} h2 {{ margin-top: 32px; }}
    .muted {{ color: #667085; }} .summary, .card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 10px #10182812; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0; }}
    .badge {{ background: #eef4ff; color: #174ea6; padding: 7px 10px; border-radius: 999px; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #eaecf0; vertical-align: top; }}
    th {{ background: #f8fafc; color: #475467; }} .score {{ font-weight: 700; color: #067647; }}
    a {{ color: #175cd3; }} .warnings {{ color: #b54708; }}
    @media (max-width: 760px) {{ table {{ display: block; overflow-x: auto; }} main {{ padding: 20px 12px 40px; }} }}
  </style>
</head>
<body><main>
  <h1>电商选品研究报告：{escape(request.category)}</h1>
  <p class="muted">研究市场：{escape(request.target_market)}　目标客群：{escape(request.target_customer)}</p>
  <div class="badges">
    {_status_badge("搜索", search_status)}
    {_status_badge("模型", model_status)}
    {_status_badge("推荐数", str(len(report_model.recommendations)))}
    {_status_badge("证据数", str(len(report_model.evidence)))}
  </div>
  <section class="summary"><h2>结论摘要</h2><p>{escape(report_model.executive_summary)}</p>
    <p><strong>当前决策状态：</strong>{escape(report_model.decision_status)}</p>
    <p class="muted">{escape(report_model.decision_basis)}</p>
    <h3>下一步动作</h3><ol>{''.join(f'<li>{escape(action)}</li>' for action in report_model.next_actions)}</ol>
  </section>
  <section class="card"><h2>一、市场概况</h2><ul>{trend_rows}</ul></section>
  <section class="card"><h2>二、竞争格局</h2><ul>{competitor_rows}</ul></section>
  <section class="card"><h2>三、价格带分析</h2><ul>{price_band_rows}</ul></section>
  <section class="card"><h2>四、目标人群匹配</h2><ul>{customer_rows}</ul></section>
  <section class="card"><h2>五、风险与进入壁垒</h2><ul>{risk_rows}</ul></section>
  <h2>六、推荐方向与验证动作</h2>
  <table><thead><tr><th>方向</th><th>定位与客群</th><th>候选价格带与依据</th><th>评分组成</th><th>理由与验证动作</th></tr></thead>
  <tbody>{recommendations or '<tr><td colspan="5">暂无推荐方向</td></tr>'}</tbody></table>
  <h2>研究证据</h2>
  <table><thead><tr><th>标题</th><th>观察摘要</th><th>来源</th><th>置信度</th><th>类型</th></tr></thead>
  <tbody>{evidence or '<tr><td colspan="5">暂无证据</td></tr>'}</tbody></table>
  <h2>运行告警</h2><section class="card">{warning_block}</section>
</main></body></html>
"""


def render_html_comparison(rows: list[dict[str, Any]]) -> str:
    """Render a compact offline comparison page for several categories."""

    table_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('category', '')))}</td>"
        f"<td>{int(row.get('recommendation_count', 0))}</td>"
        f"<td>{int(row.get('candidate_count', 0))}</td>"
        f"<td class=score>{float(row.get('average_score', 0.0)):.1f}</td>"
        f"<td>{int(row.get('warning_count', 0))}</td>"
        f"<td><a href=\"{escape(str(row.get('report_html', '')), quote=True)}\">查看报告</a></td>"
        "</tr>"
        for row in rows
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>电商选品离线对比</title>
<style>
body {{ margin: 0; background: #f5f7fb; color: #1f2937; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
main {{ max-width: 1000px; margin: 0 auto; padding: 32px 20px 56px; }}
.card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 10px #10182812; }}
table {{ width: 100%; border-collapse: collapse; background: white; overflow: hidden; }}
th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #eaecf0; }} th {{ background: #f8fafc; color: #475467; }}
.score {{ font-weight: 700; color: #067647; }} a {{ color: #175cd3; }}
</style></head><body><main>
<h1>电商选品离线对比</h1>
<p>该页面由 Mock 数据生成，用于比较工程流程，不代表真实市场事实。</p>
<section class="card"><table><thead><tr><th>品类</th><th>推荐方向</th><th>候选证据</th><th>平均评分</th><th>告警数</th><th>报告</th></tr></thead>
<tbody>{table_rows or '<tr><td colspan="6">暂无结果</td></tr>'}</tbody></table></section>
</main></body></html>"""
