"use client";

import { useMemo, useState } from "react";

import styles from "./templates.module.css";

type TemplateId = "cockpit" | "editorial" | "bento" | "console";

type Template = {
  id: TemplateId;
  name: string;
  eyebrow: string;
  description: string;
  tone: string;
  accent: string;
};

const templates: Template[] = [
  {
    id: "cockpit",
    name: "Research Cockpit",
    eyebrow: "01 / 推荐",
    description:
      "以研究状态、证据链和决策动作作为核心，适合产品演示与完整工作流。",
    tone: "深蓝 · 专业 · 信息密度适中",
    accent: "blue",
  },
  {
    id: "editorial",
    name: "Evidence Editorial",
    eyebrow: "02 / 叙事",
    description:
      "偏商业研究报告风格，强化结论、引用和验证建议，阅读节奏更舒展。",
    tone: "象牙白 · 杂志感 · 报告优先",
    accent: "coral",
  },
  {
    id: "bento",
    name: "Commerce Bento",
    eyebrow: "03 / 轻量",
    description:
      "用模块化 Bento 卡片拆解指标、推荐和风险，适合快速浏览与运营协作。",
    tone: "浅紫 · 活力 · 卡片化",
    accent: "violet",
  },
  {
    id: "console",
    name: "Operator Console",
    eyebrow: "04 / 高密度",
    description: "更像数据运营控制台，强调批量任务、实时状态和历史比较。",
    tone: "炭黑 · 紧凑 · 操作优先",
    accent: "lime",
  },
];

function PreviewFrame({ template }: { template: Template }) {
  return (
    <div className={`${styles.previewFrame} ${styles[template.id]}`}>
      <div className={styles.previewTopbar}>
        <div className={styles.previewBrand}>
          <span className={styles.previewMark}>✦</span>
          <span>
            {template.id === "editorial" ? "FIELD NOTES" : "DEERFLOW"}
          </span>
        </div>
        <div className={styles.previewTopActions}>
          <span />
          <span />
          <span />
        </div>
      </div>
      <div className={styles.previewBody}>
        {template.id === "cockpit" && (
          <>
            <div className={styles.cockpitHero}>
              <div>
                <div className={styles.previewKicker}>
                  PRODUCT RESEARCH / LIVE WORKSPACE
                </div>
                <div className={styles.previewTitle}>电商选品研究工作台</div>
                <div className={styles.previewMuted}>
                  从品类假设到证据目录，一次运行完成研究。
                </div>
              </div>
              <div className={styles.heroScore}>
                78.6<small>机会分</small>
              </div>
            </div>
            <div className={styles.cockpitGrid}>
              <div className={styles.previewPanelTall}>
                <div className={styles.panelLabel}>研究配置</div>
                <div className={styles.fakeInput}>可折叠露营桌</div>
                <div className={styles.fakeInput}>Mock 演示</div>
                <div className={styles.fakeButton}>开始研究</div>
              </div>
              <div className={styles.previewPanelTall}>
                <div className={styles.panelLabel}>首选验证方向</div>
                <div className={styles.fakeHeadline}>轻量化户外折叠桌</div>
                <div className={styles.fakeLine} />
                <div className={`${styles.fakeLine} ${styles.short}`} />
                <div className={styles.fakeEvidence}>
                  证据覆盖 86% · 风险 2 项
                </div>
              </div>
            </div>
          </>
        )}
        {template.id === "editorial" && (
          <>
            <div className={styles.editorialIntro}>
              <div className={styles.previewKicker}>
                RESEARCH MEMO · 17 AUG 2026
              </div>
              <div className={styles.editorialTitle}>
                A clearer way to
                <br />
                choose the next product.
              </div>
              <div className={styles.editorialRule} />
              <div className={styles.previewMuted}>
                一份有证据边界、有验证动作的选品研究报告。
              </div>
            </div>
            <div className={styles.editorialColumns}>
              <div>
                <div className={styles.panelLabel}>01 / 结论</div>
                <div className={styles.editorialQuote}>
                  “先验证轻量收纳与稳定承重，再扩大库存。”
                </div>
              </div>
              <div>
                <div className={styles.panelLabel}>EVIDENCE INDEX</div>
                <div className={styles.editorialStat}>
                  12 <small>条来源</small>
                </div>
                <div className={styles.fakeLine} />
                <div className={`${styles.fakeLine} ${styles.short}`} />
              </div>
            </div>
          </>
        )}
        {template.id === "bento" && (
          <>
            <div className={styles.bentoHeader}>
              <div>
                <div className={styles.previewKicker}>
                  GOOD SIGNALS / PRODUCT LAB
                </div>
                <div className={styles.previewTitle}>今天研究什么？</div>
              </div>
              <div className={styles.bentoAvatar}>ZW</div>
            </div>
            <div className={styles.bentoGrid}>
              <div className={`${styles.bentoCard} ${styles.bentoWide}`}>
                <div className={styles.panelLabel}>当前品类</div>
                <div className={styles.bentoBig}>可折叠露营桌</div>
                <div className={styles.bentoTrend}>↗ 需求代理 +18.4%</div>
              </div>
              <div className={`${styles.bentoCard} ${styles.bentoAccent}`}>
                <div className={styles.panelLabel}>机会分</div>
                <div className={styles.bentoScore}>78.6</div>
                <div className={styles.bentoMiniBar} />
              </div>
              <div className={styles.bentoCard}>
                <div className={styles.panelLabel}>推荐方向</div>
                <div className={styles.bentoProduct}>
                  轻量化
                  <br />
                  户外折叠桌
                </div>
                <div className={styles.fakeTag}>首选</div>
              </div>
              <div className={`${styles.bentoCard} ${styles.bentoWide}`}>
                <div className={styles.panelLabel}>验证动作</div>
                <div className={styles.bentoAction}>
                  小批量测试转化、退款和毛利门槛
                </div>
                <div className={styles.fakeArrow}>→</div>
              </div>
            </div>
          </>
        )}
        {template.id === "console" && (
          <>
            <div className={styles.consoleLayout}>
              <div className={styles.consoleSide}>
                <div className={styles.consoleSideActive}>⌂ 研究总览</div>
                <div>◌ 批量任务</div>
                <div>▦ 历史报告</div>
                <div>⚙ 能力设置</div>
              </div>
              <div className={styles.consoleMain}>
                <div className={styles.consoleHeader}>
                  <div>
                    <div className={styles.previewKicker}>OPERATOR CONSOLE</div>
                    <div className={styles.previewTitle}>研究任务总览</div>
                  </div>
                  <div className={styles.consoleStatus}>● MOCK READY</div>
                </div>
                <div className={styles.consoleMetrics}>
                  <div>
                    <small>运行中</small>
                    <strong>03</strong>
                  </div>
                  <div>
                    <small>已完成</small>
                    <strong>28</strong>
                  </div>
                  <div>
                    <small>平均分</small>
                    <strong>72.4</strong>
                  </div>
                </div>
                <div className={styles.consoleTable}>
                  <div className={styles.tableRow}>
                    <span>可折叠露营桌</span>
                    <span>研究完成</span>
                    <b>78.6</b>
                  </div>
                  <div className={styles.tableRow}>
                    <span>便携榨汁杯</span>
                    <span>等待运行</span>
                    <b>—</b>
                  </div>
                  <div className={styles.tableRow}>
                    <span>桌面收纳盒</span>
                    <span>部分证据</span>
                    <b>64.2</b>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function EcommerceTemplateGalleryPage() {
  const [selectedId, setSelectedId] = useState<TemplateId>("bento");
  const selected = useMemo(
    () => templates.find((item) => item.id === selectedId) ?? templates[0]!,
    [selectedId],
  );

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.header}>
          <div>
            <div className={styles.eyebrow}>DEERFLOW / TEMPLATE GALLERY</div>
            <h1>选择你的下一版研究工作台</h1>
            <p>
              先看版式与气质，再决定如何替换现有页面。当前预览不会修改正式研究流程。
            </p>
          </div>
          <a href="/ecommerce" className={styles.backLink}>
            返回当前页面 <span>↗</span>
          </a>
        </header>

        <section className={styles.selectionBar} aria-live="polite">
          <div>
            <span>当前候选</span>
            <strong>{selected.name}</strong>
            <em>{selected.tone}</em>
          </div>
          <div className={styles.selectionHint}>
            选择一个模板后，我会按此方向重排正式页面
          </div>
        </section>

        <section className={styles.gallery} aria-label="网页模板预览">
          {templates.map((template) => (
            <article
              key={template.id}
              className={`${styles.templateCard} ${selectedId === template.id ? styles.selected : ""}`}
            >
              <button
                type="button"
                className={styles.cardButton}
                onClick={() => setSelectedId(template.id)}
                aria-pressed={selectedId === template.id}
              >
                <PreviewFrame template={template} />
                <div className={styles.cardMeta}>
                  <div
                    className={`${styles.templateAccent} ${styles[template.accent]}`}
                  />
                  <div className={styles.cardMetaText}>
                    <div className={styles.cardEyebrow}>{template.eyebrow}</div>
                    <h2>{template.name}</h2>
                    <p>{template.description}</p>
                  </div>
                  <span className={styles.radio}>
                    {selectedId === template.id ? "✓" : ""}
                  </span>
                </div>
              </button>
            </article>
          ))}
        </section>

        <footer className={styles.footerNote}>
          <span>
            建议优先比较：信息密度、报告阅读节奏、配置操作效率、演示记忆点。
          </span>
          <span>
            已选：<strong>{selected.name}</strong>
          </span>
        </footer>
      </div>
    </main>
  );
}
