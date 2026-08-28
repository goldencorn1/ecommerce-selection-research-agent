from src.ecommerce.orchestration import run_mock_research
from src.ecommerce.report_export import render_html_report


def test_markdown_report_exposes_five_standalone_analysis_sections() -> None:
    result = run_mock_research(
        {
            "category": "可折叠露营桌",
            "target_market": "中国大陆电商",
            "target_customer": "周末露营的年轻家庭",
        }
    )

    for heading in (
        "## 一、市场概况",
        "## 二、竞争格局",
        "## 三、价格带分析",
        "## 四、目标人群匹配",
        "## 五、风险与进入壁垒",
        "## 六、推荐方向与验证动作",
    ):
        assert heading in result.markdown
    assert "证据 " in result.markdown
    assert "## 证据详情" in result.markdown


def test_markdown_report_contains_competition_and_price_analysis() -> None:
    result = run_mock_research({"category": "便携榨汁杯"})

    assert "红海/蓝海判断" in result.markdown
    assert "头部集中度" in result.markdown
    assert "空白价格带" in result.markdown
    assert "主流价格区间" in result.markdown
    assert "季节性" in result.markdown


def test_html_report_keeps_the_same_five_section_contract() -> None:
    report = run_mock_research({"category": "便携榨汁杯"}).report
    html = render_html_report(report)

    for heading in (
        "一、市场概况",
        "二、竞争格局",
        "三、价格带分析",
        "四、目标人群匹配",
        "五、风险与进入壁垒",
        "六、推荐方向与验证动作",
    ):
        assert heading in html
