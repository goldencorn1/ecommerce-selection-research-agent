# `src.eval` 兼容层

电商项目当前的主评测入口是 [`src/evaluation/`](../evaluation/)，负责 50 条电商评测集、规则 Judge、A3/A4 运行器和消融实验。

`src/eval/` 是 DeerFlow 上游通用报告评测接口的兼容层，保留 `ReportEvaluator`、通用指标和可选 LLM Judge，供历史代码或通用报告场景使用。新建电商评测、修改电商指标或生成正式电商评测产物时，应优先使用 `src.evaluation`。

当前未删除兼容层，以避免破坏上游导入；后续如不再有调用方，可在一次版本升级中移除，并同步更新测试和依赖。
