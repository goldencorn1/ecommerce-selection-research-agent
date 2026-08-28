# C4 商业数据闭环与演示报告（2026-08-17）

## 结论

C4 已完成。由于当前没有真实商业数据，本阶段没有虚构销量、供应商成本、库存、转化率或合规结论，而是完善了“待核验商业数据”的功能链路，并生成可直接用于演示的 `DEMO_ONLY` 数据包。

## 已完成能力

- 离线 Demo 自动生成报告指纹绑定的商业核验 JSONL。
- 每个推荐方向自动生成一条明确的 `DEMO_ONLY` 未核验记录。
- 自动执行商业核验预检，演示数据固定返回 `blocked`。
- 在 Demo summary 中显示 `commercial_decision_ready=false`，避免把占位数据误认为真实数据。
- 保留已有 Excel/CSV 导入、字段映射、报告指纹、证据关联和商业门禁。
- 快照回放继续保持外部请求数为 0。

## 演示包

已生成两品类离线演示：

```powershell
.\.venv\Scripts\python.exe main.py `
  --ecommerce-demo `
  --ecommerce-demo-dir artifacts/c4/demo `
  --ecommerce-demo-categories "可折叠露营桌,便携榨汁杯"
```

打开：`artifacts/c4/demo/index.html`

每个品类目录包含：

- `report.json`、`report.md`、`report.html`
- `candidate-catalog.json`
- `snapshot-replay.json`
- `commercial-verification-demo-only.jsonl`
- `commercial-verification-preflight.json`
- `summary.json`

## 演示时的正确叙述

1. 先展示 Mock 报告和候选证据目录。
2. 打开 `commercial-verification-demo-only.jsonl`，说明系统已经准备好承接真实商品详情、价格、销量、成本、库存和合规数据。
3. 打开预检结果，展示 `status=blocked`，说明占位数据不会放开商业决策门禁。
4. 说明未来只需要用用户有权使用的真实数据替换记录，并保留报告指纹和证据 ID。
5. 不要把 Demo 数字表述为真实市场销量、成本、库存或合规事实。

## 验收结果

- 两个品类 Demo 均生成成功。
- 每个品类 3 条 DEMO_ONLY 记录。
- 每个品类商业核验预检均为 `blocked`。
- `commercial_decision_ready` 均为 `false`。
- 17 项 C4 定向测试通过。
- 完整电商与评测回归将在本阶段收尾时再次执行。

## 下一阶段

可以进入 C5：最终演示验收与提交材料收口。重点是固定演示路径、展示 C4 的门禁边界、整理评分依据和最终交付包；真实商业数据接入保留为使用者后续配置项。
