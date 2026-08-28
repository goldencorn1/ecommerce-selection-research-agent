"""Build the formal D0 product requirements PDF with a Chinese-capable font."""

from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "PRODUCT_REQUIREMENTS_D0_2026-08-17.pdf"
FONT_PATH = Path(r"C:\Windows\Fonts\simhei.ttf")


def safe(value: str) -> str:
    return html.escape(value).replace("\n", "<br/>")


def para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(safe(text), style)


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("SimHei", 8)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 12 * mm, "选品研判台 - 正式产品需求文档 D0")
    canvas.drawRightString(192 * mm, 12 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build_pdf() -> Path:
    if not FONT_PATH.is_file():
        raise FileNotFoundError(f"Chinese font not found: {FONT_PATH}")
    pdfmetrics.registerFont(TTFont("SimHei", str(FONT_PATH)))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "D0Title", parent=styles["Title"], fontName="SimHei", fontSize=22,
        leading=30, alignment=TA_CENTER, textColor=colors.HexColor("#123B66"),
        spaceAfter=10 * mm,
    )
    subtitle = ParagraphStyle(
        "D0Subtitle", parent=styles["Normal"], fontName="SimHei", fontSize=10,
        leading=17, alignment=TA_CENTER, textColor=colors.HexColor("#475467"),
        spaceAfter=5 * mm,
    )
    h1 = ParagraphStyle(
        "D0H1", parent=styles["Heading1"], fontName="SimHei", fontSize=15,
        leading=22, textColor=colors.HexColor("#123B66"), spaceBefore=8 * mm,
        spaceAfter=4 * mm,
    )
    h2 = ParagraphStyle(
        "D0H2", parent=styles["Heading2"], fontName="SimHei", fontSize=11,
        leading=17, textColor=colors.HexColor("#155EEF"), spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle(
        "D0Body", parent=styles["BodyText"], fontName="SimHei", fontSize=9.2,
        leading=16, textColor=colors.HexColor("#344054"), wordWrap="CJK",
        alignment=TA_LEFT, spaceAfter=2.5 * mm,
    )
    bullet = ParagraphStyle(
        "D0Bullet", parent=body, leftIndent=6 * mm, firstLineIndent=-4 * mm,
        bulletIndent=0, spaceAfter=1.5 * mm,
    )
    small = ParagraphStyle(
        "D0Small", parent=body, fontSize=8.3, leading=13,
    )

    story = [
        Spacer(1, 22 * mm),
        para("选品研判台", title),
        para("正式产品需求文档", title),
        para("D0 / V1.0 | 2026-08-17 | 个人独立开发项目", subtitle),
        para("基于 DeerFlow 二次开发的电商选品研究工作台", subtitle),
        Spacer(1, 10 * mm),
        para("文档说明", h1),
        para("本 PDF 是 D0 正式提交材料，覆盖产品背景、用户问题、核心功能、非功能需求、交互流程、技术架构、里程碑和个人项目职责。开发者姓名保留为待补录字段，提交前由项目负责人填写真实信息。", body),
        para("当前产品的核心边界是：系统输出可追溯的验证优先级，而不是在缺少合法商业数据时直接给出采购、放量或销量结论。", body),
        PageBreak(),
    ]

    def section(number: str, heading: str) -> None:
        story.append(para(f"{number} {heading}", h1))

    def subsection(heading: str) -> None:
        story.append(para(heading, h2))

    def text(value: str) -> None:
        story.append(para(value, body))

    def bullets(values: list[str]) -> None:
        for value in values:
            story.append(para(f"- {value}", bullet))

    def table(rows: list[list[str]], widths: list[float]) -> None:
        data = [[para(cell, small) for cell in row] for row in rows]
        item = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        item.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2FF")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#123B66")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([Spacer(1, 2 * mm), item, Spacer(1, 3 * mm)])

    section("1", "产品名称与开发背景")
    subsection("1.1 产品名称")
    text("选品研判台（Ecommerce Research Workbench）。")
    subsection("1.2 开发背景")
    text("个人卖家和中小商家在选品时，需要在搜索引擎、电商平台、内容平台和表格之间反复切换，手工整理需求、竞品、价格和风险信息。传统流程存在信息分散、来源质量难判断、搜索摘要或模型文字容易被误认为商业事实等问题。")
    text("本产品以“先验证什么”为核心输出，将研究参数、市场趋势、竞品价格、目标客群、机会风险、证据来源、结构化评分和下一步验证动作收敛到一条可复跑链路中。")
    subsection("1.3 产品目标")
    bullets(["降低从品类假设到验证计划的研究整理成本。", "让每个推荐方向能够回溯到证据、来源和评分依据。", "区分 Mock、搜索候选证据、用户私有知识和人工商业核验。", "在外部搜索或模型失败时保留可解释的结构化降级结果。", "为合法 API 配置、用户数据导入和后续商业核验预留接口。"])
    subsection("1.4 目标用户")
    bullets(["个人电商卖家和独立站运营者。", "中小商家的选品、采购和市场调研人员。", "需要快速形成品类验证假设的产品或运营团队。", "需要演示可追溯 AI 研究流程的课程、训练营或评审场景。"])

    section("2", "用户问题与需求洞察")
    subsection("2.1 用户问题")
    bullets(["不知道应该先验证需求、价格、竞品还是供应链条件。", "搜索结果来源复杂，难以判断地域相关性、发布时间和可信度。", "AI 报告通常给出结论，却没有明确说明证据、风险和失败处理。", "真实商品销量、成本、库存和合规数据通常需要用户自行授权取得。", "多次研究结果难以回放、比较和审计。"])
    subsection("2.2 需求洞察")
    text("用户真正需要的不是一个自动宣称爆品的工具，而是一份能够回答以下问题的研究工作台：当前有哪些可验证的候选方向？这个方向的证据来自哪里？哪些结论只是模型推断或 Mock 假设？还缺哪些商业数据？下一步用什么小规模实验判断是否继续投入？")

    section("3", "核心功能需求")
    subsection("3.1 研究参数配置")
    bullets(["输入品类、目标市场、目标客群和价格范围。", "选择 Mock 离线或 Live 真实搜索模式。", "选择结构化 Mock、DeepSeek、OpenAI-compatible、通义千问、智谱、Kimi、SiliconFlow 或 Ollama。", "选择 Tavily、SearXNG、Brave、Serper 或自定义搜索服务。", "可选配置商品页面 Reader 或导入私有知识文件。", "支持页面临时 BYOK，Key 不写入报告历史和本地存储。"])
    subsection("3.2 显式多 Agent 编排")
    text("V1 采用显式八节点串行编排：Supervisor → Market → Competitor → Price → Customer → Risk → Report → Reviewer。Supervisor 负责请求校验和任务拆解，专职 Agent 负责研究模块，Report 负责合成，Reviewer 负责质量门禁。当前准确定位为显式多 Agent 串行编排，不宣称完全动态 Supervisor 路由。")
    subsection("3.3 五大报告板块")
    table([["板块", "输出内容"], ["需求与趋势", "需求场景、痛点、触发因素和趋势信号"], ["竞争与价格", "竞品、定位、价格锚点、价格带和价格依据"], ["目标客群与需求", "客群画像、需求、购买动机和证据关联"], ["机会与风险", "机会、限制、风险、缓解方案和证据不足"], ["推荐方向与验证动作", "推荐评分、定位、验证动作、阈值、补数据和失败处理"]], [42 * mm, 135 * mm])
    subsection("3.4 证据、验证和导出")
    bullets(["每条证据拥有稳定 ID、来源、摘要、置信度和支持结论。", "证据区分 Mock、私有知识、搜索候选和未知来源。", "质量审计区分接口成功、证据可用和商业决策就绪。", "生成验证卡片，支持 JSON、Markdown、HTML 导出。", "支持 CSV/Excel/TSV 预览、校验、导入、历史回放和报告对比。"])
    subsection("3.5 评测与观测")
    bullets(["V1 评测集固定为 50 条 JSONL 案例。", "支持结构、品类相关性、证据覆盖、评分有效性和降级提示质量指标。", "展示成功率、降级通过率、Judge 基线、P50/P95/P99 和人工抽检队列。", "每次 Web 研究生成匿名 Trace ID，并记录状态、错误分类和 P95。"])

    section("4", "性能及非功能需求")
    table([["类别", "需求与验收口径"], ["可运行性", "Mock 无外部依赖；Docker backend healthy；frontend HTTP 200；提供 Windows 快捷启动和 fallback UI。"], ["稳定性", "超时、有限重试、模块级降级、限流、熔断；单模块失败不阻塞报告。"], ["安全", "Key 仅当前请求使用；不进入响应、报告、日志和提交包；上传文件类型/路径/10 MB 限制。"], ["性能", "Mock CLI 单次约 13.95 ms，外部请求 0，成本 0；真实搜索、模型和商业准确率单独测量。"], ["可审计", "报告指纹、证据 ID、引用完整性、质量门禁、Trace ID、观测摘要和 manifest。"]], [32 * mm, 145 * mm])
    text("当前不将 Mock 延迟、测试通过率或自动 Judge 分数表述为真实商业性能或人工校准结果。")

    section("5", "用户交互流程")
    text("双击 Mock 启动 → 进入研究页 → 输入品类、市场和价格范围 → 选择 Mock/Live、模型和数据源 → 可选能力预检 → 一键体验 Mock 或生成报告 → 查看 Agent 过程 → 查看推荐、评分、证据和质量审计 → 查看风险与验证卡片 → 导出或导入核验数据 → 历史回放与多报告比较。")
    subsection("推荐演示")
    text("推荐品类为“可折叠露营桌”。固定五分钟演示路径见 docs/P3_FINAL_DELIVERY_RUNBOOK_2026-08-17.md；无真实商业数据时使用 Mock 与 DEMO_ONLY 商业核验材料。")

    section("6", "技术架构与数据流")
    text("Next.js Web / fallback UI → FastAPI 电商 API → LangGraph 电商研究图 → 八节点 Agent 串行编排 → Mock、搜索适配器、DeepSeek 和私有知识 → 结构化报告、证据、质量门禁、观测和历史。主要组件为 Next.js、Tailwind、Radix UI、FastAPI、LangGraph、Pydantic、SQLite、本地 artifacts 和 Docker Compose。")

    section("7", "开发里程碑")
    table([["阶段", "目标", "状态"], ["A0-A5", "基线、协议、知识、评测、策略和 Docker", "已完成"], ["B1-B6", "能力配置、BYOK、批量、报告、历史和页面视觉", "已完成"], ["C0-C5", "Demo 冻结、真实能力、质量治理、商业边界和提交包", "已完成"], ["P0-P3", "可信度、Agent、观测、演示路径、评分材料和离线包", "已完成"], ["D0", "正式 PRD、PDF、分工和口径统一", "当前阶段"], ["D1-D4", "真实证据、RAG、UX 复核和生产化", "后续计划"]], [25 * mm, 120 * mm, 32 * mm])

    section("8", "个人项目分工")
    text("本项目按个人独立开发项目提交。开发者姓名必须在正式提交前由负责人补录，系统不代填真实身份。")
    table([["角色", "姓名", "职责"], ["项目负责人/产品", "待补录", "产品定位、需求、演示和答辩材料"], ["后端与 Agent", "待补录", "FastAPI、LangGraph、研究编排和质量门禁"], ["前端与交互", "待补录", "Next.js 页面、配置、报告和交互体验"], ["评测与部署", "待补录", "50 条评测、Docker、回归测试和交付包"]], [40 * mm, 35 * mm, 102 * mm])

    section("9", "限制、未来规划与提交检查")
    text("项目不自动获得或声称拥有真实平台销量、库存、成本、转化率和 SKU 合规数据。真实数据必须通过用户有权使用的 API、页面服务或自有文件提供。")
    bullets(["补充真实搜索、模型和 RAG 的可复现实验。", "接入真实 BGE/Rerank 并进行消融评测。", "建立人工商业核验结果回流。", "增加认证、多用户隔离、密钥管理、任务队列和云部署。", "提交前补录开发者姓名，统一 V1 50 条评测口径，完成 PDF、Docker、Mock、离线 Demo 和 manifest 验收。"])

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=17 * mm, bottomMargin=19 * mm, title="选品研判台正式产品需求文档 D0",
        author="个人独立开发项目",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return OUTPUT


if __name__ == "__main__":
    print(build_pdf())
