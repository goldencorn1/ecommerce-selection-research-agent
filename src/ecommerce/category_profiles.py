"""Lightweight category profiles for deterministic offline synthesis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationVariant:
    suffix: str
    positioning: str
    rationale: str
    price_multiplier: float
    validation_action: str
    score_adjustment: float = 0.0
    price_band_width: float = 0.18
    validation_threshold: str = "7-14 天小批量测试达到可接受的转化、退款和毛利门槛"
    validation_data_needed: tuple[str, ...] = ("售价", "销量周期", "单位成本", "库存", "合规状态")
    validation_failure_action: str = "若未达标，暂停扩大库存，回到价格、规格或客群假设重新验证。"


@dataclass(frozen=True)
class CategoryProfile:
    audience: str
    trend_label: str
    trend_rationale: str
    needs: tuple[str, ...]
    pain_points: tuple[str, ...]
    buying_triggers: tuple[str, ...]
    opportunity: str
    opportunity_rationale: str
    risks: tuple[str, ...]
    mitigations: tuple[str, ...]
    variants: tuple[RecommendationVariant, ...]


_OUTDOOR = CategoryProfile(
    audience="周末露营、短途出行和家庭户外活动人群",
    trend_label="户外场景细分与轻量化",
    trend_rationale="户外用品的购买决策通常集中在收纳体积、展开效率、稳定性和多场景适配。",
    needs=("快速展开和收纳", "稳定承重", "适配车载或家庭户外场景"),
    pain_points=("体积大难收纳", "结构晃动或承重描述不清", "清洁和维护成本较高"),
    buying_triggers=("真实户外场景演示", "明确承重与尺寸参数", "便携收纳和售后保障"),
    opportunity="围绕轻量收纳、稳定承重和多场景使用打造差异化版本",
    opportunity_rationale="优先把用户可感知的展开效率、收纳体积和稳定性做成可验证指标，避免只做外观同质化。",
    risks=("结构安全和耐用性波动", "同质化竞品较多", "户外场景评价积累较慢"),
    mitigations=("做承重与疲劳测试", "首批小单验证关键部件", "用真实场景内容积累评价"),
    variants=(
        RecommendationVariant("轻量便携款", "面向短途露营和车载收纳，强调轻量折叠与快速展开", "先验证收纳体积、展开时间和基础承重", 0.9, "样品测试收纳体积、展开时间和承重", 1.0, 0.16),
        RecommendationVariant("稳定承重款", "面向家庭露营和多人使用，强调稳定性与耐用结构", "用更高稳定性换取明确的中高端溢价", 1.2, "对不同地面和负载进行稳定性测试", 2.0, 0.18),
        RecommendationVariant("场景套装款", "面向完整户外装备购买，强调桌面功能与配件组合", "通过配件组合提高客单价，但需控制套装复杂度", 1.35, "测试桌体、收纳袋和配件的组合购买率", -1.0, 0.22),
    ),
)

_STORAGE = CategoryProfile(
    audience="需要提升空间利用率的学生、白领和小户型家庭",
    trend_label="空间利用与模块化收纳",
    trend_rationale="收纳用品的核心需求来自空间适配、取用效率和长期整洁维护。",
    needs=("充分利用有限空间", "分类取用方便", "尺寸和材质适配现有家具"),
    pain_points=("尺寸不合适", "取放不顺手", "承重或清洁体验不稳定"),
    buying_triggers=("尺寸示意清晰", "真实收纳前后对比", "可叠加或组合使用"),
    opportunity="围绕空间适配、模块组合和高频取用效率打造差异化版本",
    opportunity_rationale="通过尺寸体系和组合方式建立可解释差异，而不是只依赖颜色和外观。",
    risks=("尺寸适配范围有限", "材料和承重表现不一致", "低价竞品容易跟进"),
    mitigations=("建立标准尺寸矩阵", "标注承重和适配边界", "先验证高频使用场景"),
    variants=(
        RecommendationVariant("基础分区款", "面向高频小物整理，强调低门槛和快速取用", "先用清晰分区解决最常见的整理痛点", 0.85, "测试高频物品取放效率和复购反馈", 1.0, 0.16),
        RecommendationVariant("模块扩展款", "面向持续整理需求，强调可叠加和自由组合", "通过模块化提高空间适配和连带购买机会", 1.15, "测试不同模块组合的连带购买率", 2.0, 0.18),
        RecommendationVariant("小户型套装款", "面向整体空间整理，强调多区域统一收纳", "用完整解决方案提高客单价，但需验证套装利用率", 1.3, "用小户型样板场景测试整套使用率", -1.0, 0.22),
    ),
)

_DIGITAL = CategoryProfile(
    audience="需要提升设备使用效率的通勤、办公和内容创作用户",
    trend_label="设备兼容与使用效率",
    trend_rationale="数码配件的购买决策通常取决于兼容性、稳定性、易用性和售后成本。",
    needs=("兼容常用设备", "安装和操作简单", "长期使用稳定可靠"),
    pain_points=("兼容范围不清", "安装后不稳定", "参数宣传难以验证"),
    buying_triggers=("明确兼容清单", "真实安装演示", "可靠性和售后承诺"),
    opportunity="围绕兼容边界、稳定体验和易安装设计建立差异化",
    opportunity_rationale="把兼容性和稳定性转化为可演示、可测试的卖点，减少参数堆砌。",
    risks=("协议或设备适配变化", "质量问题导致退货", "同类产品价格竞争"),
    mitigations=("建立兼容测试矩阵", "做长时间稳定性测试", "准备清晰的售后和替代方案"),
    variants=(
        RecommendationVariant("轻量入门款", "面向日常基础使用，强调兼容清晰和安装简单", "以低学习成本获得首批用户反馈", 0.9, "测试主流设备兼容率和安装成功率", 1.0, 0.16),
        RecommendationVariant("稳定升级款", "面向高频办公使用，强调稳定性和耐用性", "用可靠性解决高频用户的核心痛点", 1.2, "进行连续使用和异常场景压力测试", 2.0, 0.18),
        RecommendationVariant("多设备套装款", "面向多设备用户，强调统一配件和组合使用", "通过组合方案提高客单价和使用完整度", 1.35, "测试不同设备组合的购买偏好", -1.0, 0.22),
    ),
)

_TABLET = CategoryProfile(
    audience="学生、移动办公和内容娱乐用户",
    trend_label="学习办公一体化与移动生产力",
    trend_rationale="平板电脑的购买决策通常同时受屏幕体验、续航、生态兼容和键盘/手写配件影响，不能只用统一低价带判断。",
    needs=("满足阅读、网课或轻办公", "续航和便携性稳定", "配件与系统生态兼容"),
    pain_points=("参数很多但实际体验难比较", "键盘和手写笔增加总购买成本", "低价机型性能和售后边界不清"),
    buying_triggers=("真实应用场景演示", "明确总装备价格", "续航、重量、性能和售后可验证"),
    opportunity="围绕明确场景做总装备方案，而不是只竞争裸机参数",
    opportunity_rationale="先锁定一个高频场景和一套可控制的配件组合，再用真实任务完成率验证用户是否愿意为体验付费。",
    risks=("硬件规格更新快", "配件和系统生态形成额外成本", "品牌心智和售后门槛较高"),
    mitigations=("建立应用任务测试表", "把裸机、配件和售后成本分开核算", "先做小规模内容/投放测试"),
    variants=(
        RecommendationVariant(
            "学习入门款",
            "面向网课、阅读和基础记笔记，强调轻量、续航和低总拥有成本",
            "以明确的学习任务完成率换取入门用户，而不是只压低裸机价格",
            0.82,
            "用 10 个高频学习任务测试完成率、续航和手写/键盘刚需，再观察退货原因",
            1.0,
            0.16,
        ),
        RecommendationVariant(
            "移动办公款",
            "面向文档、会议和多任务切换，强调键盘协同、稳定性能和售后",
            "把裸机加核心配件的总价控制在用户可接受区间，验证办公任务完成效率",
            1.15,
            "用真实文档、会议和多窗口任务做 7 天试用，记录卡顿、续航和配件使用率",
            2.5,
            0.18,
        ),
        RecommendationVariant(
            "创作娱乐款",
            "面向影音、绘画和轻内容创作，强调屏幕、扬声器和手写体验组合",
            "只有在创作任务完成率和配件连带购买率成立时，才值得承担更高库存成本",
            1.48,
            "以创作任务完成率、配件连带购买率和 7 日留存作为继续投入门槛",
            -1.0,
            0.20,
        ),
    ),
)

_GENERIC = CategoryProfile(
    audience="关注实用性、耐用性和性价比的目标用户",
    trend_label="功能实用化与场景细分",
    trend_rationale="该品类需要围绕高频使用场景、核心功能和长期体验寻找差异化。",
    needs=("解决明确使用问题", "操作简单可靠", "价格与体验匹配"),
    pain_points=("功能宣传难比较", "实际体验与描述有差距", "售后和耐用性不确定"),
    buying_triggers=("场景化演示", "关键参数可验证", "明确售后和质量保障"),
    opportunity="围绕高频场景、核心功能和可验证体验打造差异化版本",
    opportunity_rationale="优先验证用户愿意付费的核心功能，再扩展外观、配件和服务差异。",
    risks=("需求规模判断偏差", "供应链质量波动", "竞品快速跟进"),
    mitigations=("先做小批量验证", "建立关键质量指标", "用真实反馈迭代产品定义"),
    variants=(
        RecommendationVariant("基础实用款", "面向高频刚需场景，强调核心功能和价格门槛", "先验证核心功能是否足以驱动购买", 0.9, "测试核心功能完成率和首批转化", 1.0, 0.16),
        RecommendationVariant("体验升级款", "面向重视体验的用户，强调耐用性和细节优化", "围绕明确体验指标建立可解释溢价", 1.2, "测试关键体验指标和溢价接受度", 2.0, 0.18),
        RecommendationVariant("场景套装款", "面向完整解决方案需求，强调组合使用和服务", "通过组合方案提高客单价，但需控制库存复杂度", 1.35, "测试套装连带购买率和库存周转", -1.0, 0.22),
    ),
)


def get_category_profile(category: str) -> CategoryProfile:
    """Return a deterministic profile selected by broad category keywords."""

    text = category.lower()
    if any(keyword in text for keyword in ("露营", "户外", "野餐", "徒步", "登山", "折叠桌")):
        return _OUTDOOR
    if any(keyword in text for keyword in ("收纳", "整理", "置物", "分区", "收纳盒", "收纳架")):
        return _STORAGE
    if any(keyword in text for keyword in ("平板", "ipad", "tablet")):
        return _TABLET
    if any(keyword in text for keyword in ("数码", "手机", "补光", "支架", "智能", "电子", "磨豆机")):
        return _DIGITAL
    return _GENERIC
