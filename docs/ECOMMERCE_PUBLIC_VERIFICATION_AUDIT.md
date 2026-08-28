# 电商公开网页替代核验记录

核验日期：2026-08-13  
核验方式：公开网页只读检查  
核验人：Codex（公开证据审计）

## 结论

本次已替代用户完成公开网页层面的初步核验，但不能替代供应商报价、平台后台销量、库存接口和合规材料审核。三个推荐方向均可保留为“条件性候选”，没有任何一个方向达到项目 `CommercialVerificationRecord.conclusion=pass` 的要求。

当前仍缺少：

- 采购或代工单位成本；
- 有明确统计周期的销量数据；
- 与具体 SKU 绑定的合规检测/材质/资质材料；
- 中国大陆目标平台上的稳定商品详情与库存证明。

## 已核验候选

### 1. 轻量便携款

- 商品：Foldable Camping Table Outdoor Beach Picnic Table Lightweight with Carry Bags
- 平台：eBay
- 详情页：[eBay item 305725478927](https://www.ebay.com/itm/305725478927)
- 页面可见信息：售价 US$25.99；页面显示 125 available、25 sold；钢制框架、可折叠，折叠尺寸约 27.6×15.7 英寸。
- 可支持判断：轻量便携、折叠和价格带的候选线索。
- 不可支持判断：近 30 天销量、单位成本、中国大陆库存、目标市场合规。
- 状态：`conditional`，不能 `pass`。

### 2. 稳定承重款

- 商品：Camping Folding Table Heavy Duty Utility Adjustable Height Portable
- 平台：eBay
- 详情页：[eBay item 397132444261](https://www.ebay.com/itm/397132444261)
- 页面可见信息：售价 US$91.10；页面标注最大承重 250 lb、钢制框架、可折叠、可调高度；页面还显示优惠价 US$86.55 的线索。
- 可支持判断：承重、钢制结构、可调高度和价格的候选线索。
- 不可支持判断：明确销量周期、当前库存数量、单位成本、中国大陆合规。
- 状态：`conditional`，不能 `pass`。

### 3. 场景套装款

- 商品：Folding camping table and chair set (7 pieces)
- 平台：eBay
- 详情页：[eBay item 406574209973](https://www.ebay.com/itm/406574209973)
- 页面可见信息：6 椅 1 桌套装；售价 US$125.99；页面显示 46 available、4 sold；可批量购买时页面还显示阶梯价格。
- 可支持判断：桌椅组合形态、套装价格和页面库存/已售文本。
- 不可支持判断：近 30 天销量、单位成本、中国大陆库存、中国大陆合规。
- 状态：`conditional`，不能 `pass`。

## 字段核验矩阵

| 方向 | 商品详情页 | 价格 | 页面库存/已售 | 统计周期销量 | 单位成本 | 合规 |
|---|---|---|---|---|---|---|
| 轻量便携款 | 已有 | 已有 | 已有 | 缺失 | 缺失 | 缺失 |
| 稳定承重款 | 已有 | 已有 | 缺失 | 缺失 | 缺失 | 缺失 |
| 场景套装款 | 已有 | 已有 | 已有 | 缺失 | 缺失 | 缺失 |

公开网页的“sold”或“available”是页面快照字段，不等于项目要求的目标市场、明确周期销量或供应链库存。因此本次审计不会把它们伪装成 `VerificationSales.period` 或 `VerificationInventory.quantity` 的商业决策数据。

## 门禁结论

本次不生成可使 `commercial_decision_ready=true` 的核验 JSONL。按项目规则，商业门禁继续关闭；下一步必须补充供应商报价/成本、目标平台周期销量和 SKU 级合规材料。

