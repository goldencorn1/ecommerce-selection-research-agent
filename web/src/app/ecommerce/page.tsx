"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { Input } from "~/components/ui/input";
import { resolveServiceURL } from "~/core/api/resolve-service-url";

import styles from "./ecommerce.module.css";

type Recommendation = {
  product_name: string;
  positioning: string;
  target_customer: string;
  price_range: string;
  rationale: string;
  validation_action: string;
  validation_threshold: string;
  validation_data_needed: string[];
  validation_failure_action: string;
  price_basis: string;
  score_note: string;
  evidence_ids?: string[];
  score: {
    total: number;
    demand: number;
    competition: number;
    margin: number;
    differentiation: number;
    evidence_quality: number;
  };
};

type Evidence = {
  evidence_id: string;
  title: string;
  source: string;
  summary: string;
  confidence: number;
  source_type?: string;
  supports?: string[];
  retrieved_at?: string | null;
  published_at?: string | null;
};

type Candidate = {
  candidate_id: string;
  title: string;
  source_domain: string;
  candidate_rank_score: number;
  source_quality_category: string;
  modules: string[];
};

type TrendSignal = {
  name: string;
  direction: string;
  demand_score: number;
  growth_rate: number;
  rationale: string;
  evidence_ids?: string[];
};

type CompetitorInsight = {
  name: string;
  price: number;
  positioning: string;
  price_source?: string;
  strengths?: string[];
  weaknesses?: string[];
  evidence_ids?: string[];
};

type CustomerProfile = {
  segment: string;
  needs?: string[];
  pain_points?: string[];
  buying_triggers?: string[];
  evidence_ids?: string[];
};

type OpportunityRisk = {
  opportunity: string;
  rationale: string;
  opportunity_score: number;
  risks?: string[];
  risk_score: number;
  mitigations?: string[];
  evidence_ids?: string[];
};

type ResearchResult = {
  report: {
    executive_summary: string;
    recommendations: Recommendation[];
    trends?: TrendSignal[];
    competitors?: CompetitorInsight[];
    customer_profiles?: CustomerProfile[];
    opportunities_risks?: OpportunityRisk[];
    evidence: Evidence[];
    warnings: string[];
    decision_status: string;
    decision_basis: string;
    next_actions: string[];
  };
  candidate_catalog: { candidates: Candidate[]; warnings: string[] };
  report_markdown: string;
  report_html: string;
  report_fingerprint: string;
  search_status: string;
  search_details?: Record<string, unknown>;
  progress_events: ProgressEvent[];
  model_status: string;
  knowledge_status?: string;
  knowledge_details?: Record<string, unknown>;
  agent_plan?: string[];
  agent_results?: Record<string, AgentResult>;
  citation_validation?: Record<string, unknown>;
  verification_validation?: Record<string, unknown>;
  quality_audit?: QualityAudit;
  trace_id?: string;
  history_id?: string;
  metrics: {
    latency_ms?: number;
    quality_level?: string;
    report_quality_gates?: Record<string, boolean>;
  };
  report_quality_gates?: Record<string, boolean>;
};

type AgentResult = {
  status?: string;
  output?: unknown;
  evidence_ids?: string[];
  warnings?: string[];
  error_kind?: string | null;
  attempts?: number;
};

type EvaluationSummary = {
  config?: {
    dataset_version?: string;
    mode?: string;
    model?: string;
    external_request_count?: number;
    total_cost_usd?: number;
    human_review_sample_count?: number;
  };
  summary?: {
    total_case_count?: number;
    measured_case_count?: number;
    success_rate?: number;
    degraded_case_count?: number;
    degradation_pass_rate?: number;
    judge_average_score?: number;
    latency_p50_ms?: number;
    latency_p95_ms?: number;
    latency_p99_ms?: number;
    metric_averages?: Record<string, number>;
    metric_pass_rates?: Record<string, number>;
  };
  human_review_pending_count?: number;
  source?: string;
};

type KnowledgeUpload = {
  filename: string;
  knowledge_file_id: string;
  record_count: number;
  size_bytes: number;
  source_type: string;
};

type ObservationSummary = {
  count?: number;
  events?: Array<{
    name?: string;
    status?: string;
    error_kind?: string | null;
  }>;
  summary?: {
    status_counts?: Record<string, number>;
    error_counts?: Record<string, number>;
    average_duration_ms?: number;
    p95_duration_ms?: number;
    traced_run_count?: number;
  };
};

type QualityAudit = {
  status?: string;
  quality_level?: string;
  gates?: Record<string, boolean>;
  report?: {
    recommendation_count?: number;
    evidence_count?: number;
    warning_count?: number;
  };
  search?: {
    total_result_count?: number;
    mainland_relevance_rate?: number;
    published_result_rate?: number;
    weighted_source_quality_score?: number;
    competitor_price_coverage?: number;
  };
  modules?: Record<
    string,
    { status?: string; result_count?: number; quality_warning_count?: number }
  >;
  model?: {
    usage_available?: boolean;
    cost_status?: string;
    actual_cost_usd?: number;
  };
  blocking_reasons?: string[];
};

type ProgressEvent = {
  event_id: string;
  stage: string;
  status: string;
  message: string;
  module?: string | null;
  metrics?: Record<string, unknown>;
};

type HistoryRow = {
  history_id: string;
  category: string;
  market: string;
  created_at: string;
  average_score: number;
  recommendation_count: number;
  candidate_count: number;
  search_status: string;
  model_status: string;
};

type ExcelPreview = {
  filename: string;
  preview: {
    status: string;
    columns: string[];
    missing_required_columns: string[];
    required_fields: string[];
    mapping_options: Record<string, string[]>;
    column_mapping: Record<string, string>;
    row_count: number;
    preview_rows: Record<string, unknown>[];
  };
};

type ProductApiPreview = {
  status?: string;
  message?: string;
  error_code?: string | null;
  provider?: string;
  endpoint?: string;
  configured?: boolean;
  reachable?: boolean;
  result_count?: number;
  products?: Array<{
    record_id?: string;
    source_id?: string;
    sku_id?: string | null;
    title?: string;
    product_url?: string | null;
    price?: number | null;
    currency?: string;
    retrieved_at?: string;
  }>;
  data_validation?: {
    status?: string;
    warnings?: string[];
    errors?: string[];
  };
  commercial_decision_ready?: boolean;
  claims_boundary?: string;
};

type ProductApiTemplate = {
  id: string;
  label: string;
  description: string;
  endpoint: string;
  method: "GET" | "POST";
  authMode: "bearer" | "header" | "none";
  header: string;
  queryParam: string;
  responsePath: string;
  fieldMap: { title: string; price: string; url: string; sku: string };
};

const PRODUCT_API_TEMPLATES: ProductApiTemplate[] = [
  {
    id: "generic-json",
    label: "通用 JSON API",
    description: "适用于返回 data[] / items[] 的标准商品接口",
    endpoint: "",
    method: "GET",
    authMode: "bearer",
    header: "Authorization",
    queryParam: "q",
    responsePath: "data",
    fieldMap: { title: "title", price: "price", url: "url", sku: "sku" },
  },
  {
    id: "demo-local",
    label: "本地 Demo 商品 API",
    description: "无需真实商业 API，可直接演示连接、映射和样品载入",
    endpoint: "http://127.0.0.1:8000/api/ecommerce/demo/product-api",
    method: "GET",
    authMode: "none",
    header: "Authorization",
    queryParam: "q",
    responsePath: "data",
    fieldMap: { title: "name", price: "price", url: "url", sku: "id" },
  },
  {
    id: "post-items",
    label: "POST items 接口",
    description: "适用于 POST JSON 并返回 items[] 的服务",
    endpoint: "",
    method: "POST",
    authMode: "header",
    header: "X-API-Key",
    queryParam: "q",
    responsePath: "items",
    fieldMap: { title: "name", price: "price", url: "product_url", sku: "id" },
  },
];

type ChartPoint = { label: string; value: number };

function MiniLineChart({ points }: { points: ChartPoint[] }) {
  if (!points.length) {
    return (
      <p className="text-sm text-slate-500">当前报告暂无足够数据生成趋势图。</p>
    );
  }
  const width = 520;
  const height = 170;
  const padding = 22;
  const maxValue = Math.max(100, ...points.map((point) => point.value));
  const xStep =
    points.length === 1 ? 0 : (width - padding * 2) / (points.length - 1);
  const coordinates = points.map((point, index) => ({
    ...point,
    x: padding + index * xStep,
    y: height - padding - (point.value / maxValue) * (height - padding * 2),
  }));
  const path = coordinates
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-40 w-full overflow-visible"
        role="img"
        aria-label="推荐方向得分趋势图"
      >
        {[25, 50, 75].map((tick) => {
          const y =
            height - padding - (tick / maxValue) * (height - padding * 2);
          return (
            <line
              key={tick}
              x1={padding}
              x2={width - padding}
              y1={y}
              y2={y}
              stroke="currentColor"
              className="text-slate-200 dark:text-slate-800"
              strokeDasharray="4 4"
            />
          );
        })}
        <path
          d={path}
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          className="text-blue-500"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {coordinates.map((point) => (
          <g key={point.label}>
            <circle
              cx={point.x}
              cy={point.y}
              r="5"
              fill="currentColor"
              className="text-blue-600"
            />
            <text
              x={point.x}
              y={height - 4}
              textAnchor="middle"
              fontSize="11"
              fill="currentColor"
              className="text-slate-500"
            >
              {point.label}
            </text>
            <text
              x={point.x}
              y={point.y - 10}
              textAnchor="middle"
              fontSize="11"
              fill="currentColor"
              className="text-slate-700 dark:text-slate-200"
            >
              {point.value.toFixed(0)}
            </text>
          </g>
        ))}
      </svg>
      <p className="text-xs text-slate-500">
        按推荐方向排列的综合评分变化，用于快速比较验证优先级。
      </p>
    </div>
  );
}

function PriceDistributionChart({ prices }: { prices: number[] }) {
  if (!prices.length) {
    return <p className="text-sm text-slate-500">当前报告暂无明确价格锚点。</p>;
  }
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const step = max === min ? 1 : (max - min) / 4;
  const bins = Array.from({ length: 4 }, (_, index) => {
    const start = min + index * step;
    const end = index === 3 ? max : start + step;
    return {
      label:
        max === min
          ? `¥${min.toFixed(0)}`
          : `¥${start.toFixed(0)}–${end.toFixed(0)}`,
      count: prices.filter(
        (price) => price >= start && (index === 3 ? price <= end : price < end),
      ).length,
    };
  });
  const maxCount = Math.max(1, ...bins.map((bin) => bin.count));
  return (
    <div className="space-y-3">
      <div className="flex h-40 items-end gap-2 rounded-xl bg-slate-50 px-3 pt-5 pb-3 dark:bg-slate-950/60">
        {bins.map((bin) => (
          <div
            key={bin.label}
            className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1"
          >
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
              {bin.count}
            </span>
            <div
              className="w-full rounded-t-md bg-cyan-400/80"
              style={{
                height: `${Math.max(8, (bin.count / maxCount) * 100)}%`,
              }}
            />
            <span className="w-full truncate text-center text-[10px] text-slate-500">
              {bin.label}
            </span>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-500">
        根据搜索模块返回的价格锚点统计，帮助识别主要价格带。
      </p>
    </div>
  );
}

type CapabilityEntry = {
  id: string;
  label: string;
  provider?: string;
  model?: string;
  configured: boolean;
  reachable: boolean | null;
  request_supported: boolean;
  reason?: string | null;
};

type CapabilityKind = "search" | "model" | "data";
type PreflightResult = "success" | "error";
type RequiredCapability = {
  item: CapabilityEntry;
  kind: CapabilityKind;
  prefix: string;
};

type ModelPreset = {
  id: string;
  label: string;
  provider: ModelProviderId;
  base_url: string;
  model: string;
  requires_api_key: boolean;
  description: string;
};

type EcommerceCapabilities = {
  status: string;
  capabilities: {
    active_search_provider?: string;
    search_providers: CapabilityEntry[];
    models: CapabilityEntry[];
    model_presets?: ModelPreset[];
    data_sources?: CapabilityEntry[];
  };
};

type ModelProviderId = "mock" | "deepseek" | "openai_compatible" | "ollama";

const FALLBACK_MODEL_PRESETS: ModelPreset[] = [
  {
    id: "mock",
    label: "结构化 Mock",
    provider: "mock",
    base_url: "",
    model: "mock",
    requires_api_key: false,
    description: "离线演示，不调用外部模型服务",
  },
  {
    id: "deepseek",
    label: "DeepSeek",
    provider: "deepseek",
    base_url: "https://api.deepseek.com",
    model: "deepseek-v4-flash",
    requires_api_key: true,
    description: "DeepSeek OpenAI-compatible 接口",
  },
  {
    id: "openai",
    label: "OpenAI",
    provider: "openai_compatible",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    requires_api_key: true,
    description: "OpenAI 官方兼容接口模板",
  },
  {
    id: "qwen",
    label: "通义千问 / DashScope",
    provider: "openai_compatible",
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
    requires_api_key: true,
    description: "DashScope OpenAI-compatible 接口模板",
  },
  {
    id: "zhipu",
    label: "智谱 GLM",
    provider: "openai_compatible",
    base_url: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-flash",
    requires_api_key: true,
    description: "智谱开放平台兼容接口模板",
  },
  {
    id: "moonshot",
    label: "月之暗面 Kimi",
    provider: "openai_compatible",
    base_url: "https://api.moonshot.cn/v1",
    model: "moonshot-v1-8k",
    requires_api_key: true,
    description: "Kimi OpenAI-compatible 接口模板",
  },
  {
    id: "siliconflow",
    label: "SiliconFlow",
    provider: "openai_compatible",
    base_url: "https://api.siliconflow.cn/v1",
    model: "deepseek-ai/DeepSeek-V3",
    requires_api_key: true,
    description: "多模型聚合兼容接口模板",
  },
  {
    id: "ollama",
    label: "Ollama 本地模型",
    provider: "ollama",
    base_url: "http://localhost:11434/v1",
    model: "qwen2.5:7b",
    requires_api_key: false,
    description: "本机 Ollama OpenAI-compatible 接口",
  },
  {
    id: "custom",
    label: "自定义 OpenAI-Compatible",
    provider: "openai_compatible",
    base_url: "",
    model: "",
    requires_api_key: true,
    description: "填写任意兼容 Chat Completions 的服务",
  },
];

type BYOKPayload = {
  model_api_key?: string;
  model_base_url?: string;
  model_name?: string;
  search_api_key?: string;
  data_api_key?: string;
};

type BatchItem = {
  item_id: string;
  category: string;
  status: string;
  attempts: number;
  history_id?: string | null;
  average_score?: number;
  recommendation_count?: number;
  candidate_count?: number;
  search_status?: string;
  model_status?: string;
  error?: { code?: string; type?: string; message?: string } | null;
};

type BatchTask = {
  task_id: string;
  status: string;
  mode: string;
  model: string;
  counts: {
    total: number;
    completed: number;
    failed: number;
    cancelled: number;
    running: number;
  };
  items: BatchItem[];
};

const DEFAULT_CATEGORY = "可折叠露营桌";
type SearchProviderId =
  "tavily" | "searxng" | "brave" | "serper" | "custom_http_json";

function isSearchProviderId(
  value: string | undefined,
): value is SearchProviderId {
  return ["tavily", "searxng", "brave", "serper", "custom_http_json"].includes(
    value ?? "",
  );
}

const FIELD_LABELS: Record<string, string> = {
  recommendation_id: "推荐方向",
  product_name: "商品名称",
  platform: "销售平台",
  detail_page_url: "商品链接",
  verifier: "核验人",
  verified_at: "核验时间",
  price_amount: "售价",
  sales_value: "销量",
  sales_period: "销量周期",
  cost_unit: "单位成本",
  inventory_status: "库存状态",
  compliance_status: "合规状态",
  conclusion: "结论",
  evidence_ids: "证据ID",
};

function scoreItems(item: Recommendation) {
  return [
    ["需求", item.score.demand],
    ["竞争", item.score.competition],
    ["利润", item.score.margin],
    ["差异", item.score.differentiation],
    ["证据", item.score.evidence_quality],
  ] as const;
}

function formatDisplayValue(value: unknown, fallback = "-"): string {
  if (value == null) return fallback;
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean" ||
    typeof value === "bigint"
  ) {
    return String(value);
  }
  try {
    return JSON.stringify(value) ?? fallback;
  } catch {
    return fallback;
  }
}

const DECISION_LABELS: Record<string, string> = {
  validate_first: "先验证再放量",
  insufficient_evidence: "证据不足",
  ready_for_scale: "可考虑放量",
};

const RUN_STATUS_LABELS: Record<string, string> = {
  success: "已完成",
  partial: "部分完成",
  error: "失败",
  mock: "Mock 离线",
  not_used: "未使用",
  not_configured: "未配置",
  fallback: "已降级",
};

const AGENT_LABELS: Record<string, string> = {
  supervisor: "Supervisor 任务拆解",
  market: "市场与趋势",
  competitor: "竞品分析",
  price: "价格分析",
  customer: "目标客群",
  risk: "机会与风险",
  report: "报告汇总",
  reviewer: "Reviewer 质量门禁",
};

const SOURCE_TYPE_LABELS: Record<string, string> = {
  mock: "Mock 代理证据",
  local: "私有知识库",
  tavily: "Tavily 搜索",
  searxng: "SearXNG 搜索",
  brave: "Brave 搜索",
  serper: "Serper 搜索",
  search: "搜索候选证据",
  unknown: "来源待确认",
};

const EVALUATION_METRIC_LABELS: Record<string, string> = {
  category_relevance: "品类相关性",
  evidence_coverage: "证据覆盖率",
  report_completeness: "报告完整率",
  score_validity: "评分有效性",
  structured_output_validity: "结构化有效率",
  degradation_warning_quality: "降级提示质量",
};

const QUALITY_GATE_LABELS: Record<string, string> = {
  interface_success: "接口成功",
  evidence_usable: "证据可用",
  commercial_decision_ready: "商业决策就绪",
};

const QUALITY_STATUS_LABELS: Record<string, string> = {
  commercial_ready: "商业核验通过",
  review_required: "需要复核",
  degraded: "已降级",
};

function humanizeStatus(value: string | undefined): string {
  if (!value) return "未知";
  return RUN_STATUS_LABELS[value] ?? value;
}

function humanizeDecision(value: string): string {
  return DECISION_LABELS[value] ?? value;
}

function formatPercent(value: number | undefined): string {
  return value == null ? "-" : `${(value * 100).toFixed(1)}%`;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "时间未记录";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}

function sourceTypeLabel(value: string | undefined): string {
  return SOURCE_TYPE_LABELS[value ?? "unknown"] ?? value ?? "来源待确认";
}

function qualityStatusLabel(value: string | undefined): string {
  return QUALITY_STATUS_LABELS[value ?? ""] ?? value ?? "未评估";
}

export default function EcommerceWorkspacePage() {
  const [category, setCategory] = useState(DEFAULT_CATEGORY);
  const [batchCategories, setBatchCategories] = useState("");
  const [market, setMarket] = useState("中国大陆电商");
  const [customer, setCustomer] = useState("");
  const [priceMin, setPriceMin] = useState("99");
  const [priceMax, setPriceMax] = useState("299");
  const [mode, setMode] = useState<"mock" | "live">("mock");
  const [model, setModel] = useState<ModelProviderId>("mock");
  const [modelPreset, setModelPreset] = useState("mock");
  const [modelEnabled, setModelEnabled] = useState(false);
  const [dataSource, setDataSource] = useState<"none" | "infoquest">("none");
  const [searchProvider, setSearchProvider] =
    useState<SearchProviderId>("tavily");
  const [searchEndpoint, setSearchEndpoint] = useState("");
  const [modelApiKey, setModelApiKey] = useState("");
  const [modelBaseUrl, setModelBaseUrl] = useState("");
  const [modelName, setModelName] = useState("");
  const [searchApiKey, setSearchApiKey] = useState("");
  const [dataApiKey, setDataApiKey] = useState("");
  const [productApiProvider, setProductApiProvider] = useState("用户商品 API");
  const [productApiEnabled, setProductApiEnabled] = useState(false);
  const [productApiTemplate, setProductApiTemplate] = useState("generic-json");
  const [productApiEndpoint, setProductApiEndpoint] = useState("");
  const [productApiMethod, setProductApiMethod] = useState<"GET" | "POST">(
    "GET",
  );
  const [productApiAuthMode, setProductApiAuthMode] = useState<
    "bearer" | "header" | "none"
  >("bearer");
  const [productApiKey, setProductApiKey] = useState("");
  const [productApiHeader, setProductApiHeader] = useState("Authorization");
  const [productApiQueryParam, setProductApiQueryParam] = useState("q");
  const [productApiResponsePath, setProductApiResponsePath] = useState("data");
  const [productApiFieldMap, setProductApiFieldMap] = useState({
    title: "title",
    price: "price",
    url: "url",
    sku: "sku",
  });
  const [productApiPreview, setProductApiPreview] =
    useState<ProductApiPreview | null>(null);
  const [productApiStatus, setProductApiStatus] = useState("");
  const [knowledgeUpload, setKnowledgeUpload] =
    useState<KnowledgeUpload | null>(null);
  const [knowledgeStatus, setKnowledgeStatus] = useState("");
  const [parallel, setParallel] = useState(false);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [evaluationSummary, setEvaluationSummary] =
    useState<EvaluationSummary | null>(null);
  const [observationSummary, setObservationSummary] =
    useState<ObservationSummary | null>(null);
  const [activeReportSection, setActiveReportSection] = useState<
    | "summary"
    | "evidence"
    | "market"
    | "competitive"
    | "price"
    | "customer"
    | "risk"
    | "action"
  >("summary");
  const [capabilities, setCapabilities] =
    useState<EcommerceCapabilities | null>(null);
  // `configured` only describes server-side environment configuration. Keep
  // request-scoped preflight results separately so a BYOK key can immediately
  // make the matching capability appear available in this page.
  const [preflightResults, setPreflightResults] = useState<
    Record<string, PreflightResult>
  >({});
  const [preflightStatus, setPreflightStatus] = useState("");
  const [isPreflighting, setIsPreflighting] = useState(false);
  const [selectedHistory, setSelectedHistory] = useState<string[]>([]);
  const [comparison, setComparison] = useState<HistoryRow[]>([]);
  const [excelPreview, setExcelPreview] = useState<ExcelPreview | null>(null);
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [excelMapping, setExcelMapping] = useState<Record<string, string>>({});
  const [excelValidation, setExcelValidation] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [excelImportStatus, setExcelImportStatus] = useState("");
  const [progressStep, setProgressStep] = useState("准备研究参数");
  const [isRunning, setIsRunning] = useState(false);
  const [batchTask, setBatchTask] = useState<BatchTask | null>(null);
  const [isBatchRunning, setIsBatchRunning] = useState(false);
  const [error, setError] = useState("");
  const [workspaceId] = useState(() => {
    if (typeof window === "undefined") return "local-user";
    const key = "deerflow-ecommerce-workspace";
    const current = window.localStorage.getItem(key);
    if (current) return current;
    const created = window.crypto?.randomUUID?.() ?? `local-${Date.now()}`;
    window.localStorage.setItem(key, created);
    return created;
  });
  const [workspaceToken, setWorkspaceToken] = useState("");

  const workspaceHeaders = useCallback(
    (extra: Record<string, string> = {}) => ({
      "X-Workspace-Id": workspaceId,
      ...(workspaceToken ? { "X-Workspace-Token": workspaceToken } : {}),
      ...extra,
    }),
    [workspaceId, workspaceToken],
  );

  const availableModelPresets =
    capabilities?.capabilities.model_presets ?? FALLBACK_MODEL_PRESETS;

  function activeModel(): ModelProviderId {
    return modelEnabled && model !== "mock" ? model : "mock";
  }

  function capabilityKey(kind: CapabilityKind, id: string): string {
    return `${kind}:${id}`;
  }

  function capabilityDisplay(
    item: CapabilityEntry,
    kind: CapabilityKind,
  ): { status: "configured" | "unconfigured" | "error"; label: string } {
    const preflight = preflightResults[capabilityKey(kind, item.id)];
    if (preflight === "success") return { status: "configured", label: "可用" };
    if (preflight === "error") return { status: "error", label: "不可用" };
    return {
      status: item.configured ? "configured" : "unconfigured",
      label: item.configured ? "已配置" : "未配置",
    };
  }

  function clearPreflightResults() {
    setPreflightResults({});
  }

  function requiredCapabilities(): RequiredCapability[] {
    if (!capabilities) return [];
    const required: RequiredCapability[] = [];
    const currentModel = activeModel();

    if (mode === "live") {
      const search = capabilities.capabilities.search_providers.find(
        (item) => item.id === searchProvider,
      );
      if (search)
        required.push({ item: search, kind: "search", prefix: "搜索" });
    }

    // Mock is the model requirement for offline mode. In live mode it is an
    // internal fallback, so only show an external model when it is enabled.
    if (mode !== "live" || currentModel !== "mock") {
      const modelItem = capabilities.capabilities.models.find(
        (item) => item.id === currentModel,
      );
      if (modelItem)
        required.push({ item: modelItem, kind: "model", prefix: "模型" });
    }

    if (dataSource === "infoquest") {
      const data = capabilities.capabilities.data_sources?.find(
        (item) => item.id === dataSource,
      );
      if (data) required.push({ item: data, kind: "data", prefix: "数据增强" });
    }

    return required;
  }

  function selectedModelPreset(): ModelPreset {
    return (
      availableModelPresets.find((preset) => preset.id === modelPreset) ??
      FALLBACK_MODEL_PRESETS[0]!
    );
  }

  function selectModelPreset(presetId: string) {
    const preset =
      availableModelPresets.find((item) => item.id === presetId) ??
      FALLBACK_MODEL_PRESETS[0]!;
    setModelPreset(preset.id);
    setModel(preset.provider);
    setModelBaseUrl(preset.base_url);
    setModelName(preset.model);
    setModelEnabled(preset.provider !== "mock");
    clearPreflightResults();
    setPreflightStatus(
      preset.provider === "mock"
        ? "已切换到离线 Mock；启用外部模型前请填写 Key 并运行能力预检。"
        : `已载入 ${preset.label} 配置模板，请填写 API Key 后启用。`,
    );
  }

  function buildBYOKPayload(): BYOKPayload | undefined {
    const payload: BYOKPayload = {};
    if (activeModel() !== "mock") {
      if (modelApiKey.trim()) payload.model_api_key = modelApiKey.trim();
      if (modelBaseUrl.trim()) payload.model_base_url = modelBaseUrl.trim();
      if (modelName.trim()) payload.model_name = modelName.trim();
    }
    if (searchApiKey.trim()) payload.search_api_key = searchApiKey.trim();
    if (dataApiKey.trim()) payload.data_api_key = dataApiKey.trim();
    return Object.keys(payload).length ? payload : undefined;
  }

  function clearBYOK() {
    setModelApiKey("");
    setModelBaseUrl("");
    setModelName("");
    setModelEnabled(false);
    setSearchApiKey("");
    setDataApiKey("");
    clearPreflightResults();
    setPreflightStatus("已清除本次页面配置；服务端 .env 配置仍保持不变。 ");
  }

  function clearProductApi() {
    setProductApiEnabled(false);
    setProductApiTemplate("generic-json");
    setProductApiEndpoint("");
    setProductApiKey("");
    setProductApiPreview(null);
    setProductApiStatus("已清除本次商品 API 配置；密钥未写入浏览器存储。 ");
  }

  function applyProductApiTemplate(templateId: string) {
    const template = PRODUCT_API_TEMPLATES.find(
      (item) => item.id === templateId,
    );
    if (!template) return;
    setProductApiTemplate(template.id);
    setProductApiEndpoint(template.endpoint);
    setProductApiMethod(template.method);
    setProductApiAuthMode(template.authMode);
    setProductApiHeader(template.header);
    setProductApiQueryParam(template.queryParam);
    setProductApiResponsePath(template.responsePath);
    setProductApiFieldMap(template.fieldMap);
    setProductApiEnabled(false);
    setProductApiPreview(null);
    setProductApiStatus(`已载入“${template.label}”配置模板，请检查并启用。`);
  }

  const loadHistory = useCallback(async () => {
    try {
      const response = await fetch(resolveServiceURL("ecommerce/history"), {
        headers: workspaceHeaders(),
      });
      if (!response.ok) return;
      const payload = (await response.json()) as { reports: HistoryRow[] };
      setHistory(payload.reports ?? []);
    } catch {
      setError("历史报告暂时无法读取；不影响新建 Mock 报告。");
    }
  }, [workspaceHeaders]);

  const loadCapabilities = useCallback(async () => {
    try {
      const response = await fetch(resolveServiceURL("ecommerce/capabilities"));
      if (!response.ok) return;
      const payload = (await response.json()) as EcommerceCapabilities;
      setCapabilities(payload);
      const activeProvider = payload.capabilities.active_search_provider;
      if (isSearchProviderId(activeProvider)) setSearchProvider(activeProvider);
    } catch {
      setPreflightStatus("能力状态暂时无法读取；Mock 模式仍可使用。 ");
    }
  }, []);

  const loadEvaluationSummary = useCallback(async () => {
    try {
      const response = await fetch(
        resolveServiceURL("ecommerce/evaluation-summary"),
      );
      if (!response.ok) return;
      setEvaluationSummary((await response.json()) as EvaluationSummary);
    } catch {
      // Evaluation artifacts are optional for the running demo.
    }
  }, []);

  const loadObservationSummary = useCallback(async () => {
    try {
      const response = await fetch(
        resolveServiceURL("ecommerce/observability?limit=20"),
      );
      if (!response.ok) return;
      setObservationSummary((await response.json()) as ObservationSummary);
    } catch {
      // Local observability is optional for the offline UI.
    }
  }, []);

  useEffect(() => {
    void fetch(resolveServiceURL("ecommerce/session"), {
      headers: { "X-Workspace-Id": workspaceId },
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: { workspace_token?: string | null } | null) => {
        if (payload?.workspace_token)
          setWorkspaceToken(payload.workspace_token);
      })
      .catch(() => {
        // Anonymous local mode does not require a session token.
      });
    void loadHistory();
    void loadCapabilities();
    void loadEvaluationSummary();
    void loadObservationSummary();
  }, [
    loadCapabilities,
    loadEvaluationSummary,
    loadHistory,
    loadObservationSummary,
    workspaceId,
  ]);

  useEffect(() => {
    if (!isRunning) return;
    const steps = [
      "校验研究参数",
      "执行搜索模块",
      "整理来源与价格",
      "生成评分与报告",
    ];
    let index = 0;
    setProgressStep(steps[0] ?? "准备研究参数");
    const timer = window.setInterval(() => {
      index = Math.min(index + 1, steps.length - 1);
      setProgressStep(steps[index] ?? "生成评分与报告");
    }, 1500);
    return () => window.clearInterval(timer);
  }, [isRunning]);

  const averageScore = useMemo(() => {
    if (!result?.report.recommendations.length) return 0;
    return (
      result.report.recommendations.reduce(
        (sum, item) => sum + item.score.total,
        0,
      ) / result.report.recommendations.length
    );
  }, [result]);

  const priceHint = useMemo(() => {
    const normalized = category.toLowerCase();
    if (
      normalized.includes("平板") ||
      normalized.includes("ipad") ||
      normalized.includes("tablet")
    ) {
      return "平板电脑可先用 ¥999–¥4999 做搜索筛选；最终推荐价带会根据竞品锚点重新计算。";
    }
    if (
      normalized.includes("露营") ||
      normalized.includes("户外") ||
      normalized.includes("折叠桌")
    ) {
      return "露营桌可先用 ¥99–¥999 做搜索筛选；最终推荐价带会根据竞品锚点重新计算。";
    }
    return "这里是搜索筛选范围，不是最终推荐价带；最终价格会结合竞品价格锚点计算。";
  }, [category]);

  const searchModules = useMemo(() => {
    const details = result?.search_details ?? {};
    const source = (details.module_status ?? details) as Record<
      string,
      unknown
    >;
    return Object.entries(source).filter(
      ([, value]) => value && typeof value === "object",
    ) as [string, Record<string, unknown>][];
  }, [result]);

  const reportChartData = useMemo(() => {
    if (!result) return { trend: [] as ChartPoint[], prices: [] as number[] };
    const trend = result.report.recommendations.map((item, index) => ({
      label: `方向 ${index + 1}`,
      value: Math.max(0, Math.min(100, item.score.total)),
    }));
    let prices = searchModules.flatMap(([, details]) =>
      Array.isArray(details.price_anchor_values)
        ? details.price_anchor_values
            .map((price) => Number(price))
            .filter((price) => Number.isFinite(price) && price > 0)
        : [],
    );
    if (!prices.length) {
      prices = result.report.recommendations.flatMap((item) => {
        const values =
          item.price_range.match(/\d+(?:\.\d+)?/g)?.map(Number) ?? [];
        const first = values[0];
        const second = values[1];
        if (first != null && second != null) return [(first + second) / 2];
        return values.length === 1 ? values : [];
      });
    }
    return { trend, prices };
  }, [result, searchModules]);

  async function uploadKnowledgeFile(file: File) {
    setKnowledgeStatus("正在解析私有知识文件…");
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(
      resolveServiceURL("ecommerce/knowledge/upload"),
      {
        method: "POST",
        headers: workspaceHeaders(),
        body: form,
      },
    );
    const payload = (await response.json()) as KnowledgeUpload & {
      detail?: string;
    };
    if (!response.ok) throw new Error(payload.detail ?? "私有知识文件上传失败");
    setKnowledgeUpload(payload);
    setKnowledgeStatus(
      `已载入 ${payload.filename}：${payload.record_count} 条记录；下次研究会作为候选私有证据参与。`,
    );
  }

  async function preflightProductApi() {
    if (!productApiEnabled) {
      setError("请先启用商品 API 配置，再运行预检。");
      return;
    }
    if (!productApiEndpoint.trim()) {
      setError("请先填写商品 API Endpoint");
      return;
    }
    setError("");
    setProductApiPreview(null);
    setProductApiStatus("正在连接用户商品 API，并读取少量样品…");
    try {
      const response = await fetch(
        resolveServiceURL("ecommerce/authorized-data/product-api/preflight"),
        {
          method: "POST",
          headers: workspaceHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            config: {
              provider: productApiProvider ?? "用户商品 API",
              endpoint: productApiEndpoint.trim(),
              method: productApiMethod,
              auth_mode: productApiAuthMode,
              api_key: productApiKey.trim() || null,
              auth_header_name: productApiHeader.trim() || "Authorization",
              query_param: productApiQueryParam.trim() || "q",
              category,
              response_path: productApiResponsePath.trim(),
              field_map: productApiFieldMap,
              max_results: 10,
              authorization_status: "user_declared",
              authorization_reference: "user-declared",
              allowed_use: "用户声明已获授权的商品数据读取",
            },
          }),
        },
      );
      const payload = (await response.json()) as ProductApiPreview & {
        detail?: string;
      };
      if (!response.ok) {
        throw new Error(payload.detail ?? "商品 API 配置或预检失败");
      }
      setProductApiPreview(payload);
      setProductApiStatus(payload.message ?? "商品 API 预检完成。");
    } catch (reason) {
      setProductApiStatus("");
      throw reason;
    }
  }

  async function importProductApiSample() {
    const products = productApiPreview?.products ?? [];
    if (!products.length) {
      setError("请先成功预检商品 API，并确认返回了商品样品。");
      return;
    }
    const rows = products.map((product, index) => ({
      record_id: product.record_id ?? `product-api-${index + 1}`,
      product: product.title ?? "",
      title: product.title ?? "",
      sku: product.sku_id ?? "",
      price: product.price ?? null,
      source_file: `product-api:${productApiProvider ?? "user"}`,
      updated_at: product.retrieved_at ?? new Date().toISOString(),
      content: JSON.stringify(product, null, 0),
    }));
    const file = new File(
      [rows.map((row) => JSON.stringify(row)).join("\n")],
      "product-api-sample.jsonl",
      { type: "application/x-ndjson" },
    );
    await uploadKnowledgeFile(file);
    setProductApiStatus(
      `已将 ${rows.length} 条 API 样品载入本次研究的私有知识库；生成报告时会作为候选证据参与。`,
    );
  }

  async function runResearch(
    overrides: Partial<{
      mode: "mock" | "live";
      model: ModelProviderId;
      dataSource: "none" | "infoquest";
      byok: BYOKPayload | null | undefined;
    }> = {},
  ) {
    setIsRunning(true);
    setError("");
    try {
      const requestMode = overrides.mode ?? mode;
      const requestModel = overrides.model ?? activeModel();
      const requestDataSource = overrides.dataSource ?? dataSource;
      const response = await fetch(resolveServiceURL("ecommerce/research"), {
        method: "POST",
        headers: {
          ...workspaceHeaders({ "Content-Type": "application/json" }),
        },
        body: JSON.stringify({
          category,
          market,
          customer: customer || null,
          price_min: Number(priceMin),
          price_max: Number(priceMax),
          mode: requestMode,
          model: requestModel,
          data_source: requestDataSource,
          search_provider: searchProvider,
          search_endpoint: searchEndpoint || null,
          byok: overrides.byok ?? buildBYOKPayload(),
          knowledge_file_id: knowledgeUpload?.knowledge_file_id ?? null,
          search_parallel: parallel,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "研究运行失败");
      setResult(payload as ResearchResult);
      await loadHistory();
      void loadObservationSummary();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "研究运行失败");
    } finally {
      setIsRunning(false);
    }
  }

  async function runMockDemo() {
    setMode("mock");
    setModel("mock");
    setModelPreset("mock");
    setModelEnabled(false);
    setDataSource("none");
    setKnowledgeUpload(null);
    clearPreflightResults();
    setPreflightStatus("已切换到 Mock 离线演示，正在生成示例报告…");
    await runResearch({
      mode: "mock",
      model: "mock",
      dataSource: "none",
      byok: {},
    });
  }

  async function runBatchResearch() {
    const categories = batchCategories
      .split(/[\n,，]/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (categories.length < 2) {
      setError("批量研究至少需要输入两个品类，每行一个。 ");
      return;
    }
    setIsBatchRunning(true);
    setError("");
    try {
      const response = await fetch(resolveServiceURL("ecommerce/batch"), {
        method: "POST",
        headers: {
          ...workspaceHeaders({ "Content-Type": "application/json" }),
        },
        body: JSON.stringify({
          items: categories.map((item) => ({
            category: item,
            market,
            customer: customer || null,
            price_min: Number(priceMin),
            price_max: Number(priceMax),
          })),
          mode,
          model: activeModel(),
          data_source: dataSource,
          search_provider: searchProvider,
          search_endpoint: searchEndpoint || null,
          byok: buildBYOKPayload(),
          knowledge_file_id: knowledgeUpload?.knowledge_file_id ?? null,
          search_parallel: parallel,
          max_concurrency: 2,
        }),
      });
      const payload = (await response.json()) as {
        task?: BatchTask;
        detail?: string;
      };
      if (!response.ok || !payload.task) {
        throw new Error(payload.detail ?? "批量研究提交失败");
      }
      setBatchTask(payload.task);
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        const statusResponse = await fetch(
          resolveServiceURL(`ecommerce/batch/${payload.task.task_id}`),
          { headers: workspaceHeaders() },
        );
        const statusPayload = (await statusResponse.json()) as {
          task: BatchTask;
        };
        if (!statusResponse.ok) throw new Error("批量任务状态读取失败");
        setBatchTask(statusPayload.task);
        if (
          ["success", "partial", "error", "cancelled"].includes(
            statusPayload.task.status,
          )
        ) {
          break;
        }
      }
      await loadHistory();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "批量研究运行失败");
    } finally {
      setIsBatchRunning(false);
    }
  }

  async function cancelBatchResearch() {
    if (!batchTask) return;
    const response = await fetch(
      resolveServiceURL(`ecommerce/batch/${batchTask.task_id}/cancel`),
      {
        method: "POST",
        headers: workspaceHeaders(),
      },
    );
    const payload = (await response.json()) as {
      task: BatchTask;
      detail?: string;
    };
    if (!response.ok) throw new Error(payload.detail ?? "批量任务取消失败");
    setBatchTask(payload.task);
  }

  async function retryBatchResearch() {
    if (!batchTask) return;
    const response = await fetch(
      resolveServiceURL(`ecommerce/batch/${batchTask.task_id}/retry`),
      {
        method: "POST",
        headers: workspaceHeaders(),
      },
    );
    const payload = (await response.json()) as {
      task?: BatchTask;
      detail?: string;
    };
    if (!response.ok || !payload.task)
      throw new Error(payload.detail ?? "失败项重试提交失败");
    setBatchCategories(
      payload.task.items.map((item) => item.category).join("\n"),
    );
    setBatchTask(payload.task);
    setIsBatchRunning(true);
    try {
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        const statusResponse = await fetch(
          resolveServiceURL(`ecommerce/batch/${payload.task.task_id}`),
          { headers: workspaceHeaders() },
        );
        const statusPayload = (await statusResponse.json()) as {
          task: BatchTask;
        };
        if (!statusResponse.ok) throw new Error("批量重试状态读取失败");
        setBatchTask(statusPayload.task);
        if (
          ["success", "partial", "error", "cancelled"].includes(
            statusPayload.task.status,
          )
        )
          break;
      }
      await loadHistory();
    } finally {
      setIsBatchRunning(false);
    }
  }

  async function runPreflight() {
    setIsPreflighting(true);
    setPreflightStatus("正在检查当前搜索源和模型连接…");
    try {
      const selectedModel = activeModel();
      const needsSearch = mode === "live";
      const needsModel = selectedModel !== "mock";
      const needsData = dataSource === "infoquest";
      const provider =
        needsData || (needsSearch && needsModel)
          ? "all"
          : needsSearch
            ? "search"
            : needsModel
              ? "model"
              : "model";
      const response = await fetch(resolveServiceURL("ecommerce/preflight"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          model: selectedModel,
          data_source: dataSource,
          search_provider: searchProvider,
          search_endpoint: searchEndpoint || null,
          byok: buildBYOKPayload(),
          max_results: 3,
        }),
      });
      const payload = (await response.json()) as {
        status?: string;
        failed?: string[];
        checks?: Record<
          string,
          { status?: string; message?: string; error_code?: string }
        >;
        detail?: string | { msg?: string }[];
      };
      if (!response.ok) {
        const detail =
          typeof payload.detail === "string"
            ? payload.detail
            : Array.isArray(payload.detail)
              ? payload.detail
                  .map((item) => item.msg)
                  .filter(Boolean)
                  .join("；")
              : "未返回具体原因";
        throw new Error(
          `能力预检请求失败（HTTP ${response.status}）：${detail}`,
        );
      }
      const failed = Array.isArray(payload.failed) ? payload.failed : [];
      const checks = payload.checks ?? {};
      setPreflightResults((current) => {
        const next = { ...current };
        const checkTargets: Array<{
          kind: CapabilityKind;
          id: string;
          check: string;
        }> = [
          { kind: "search", id: searchProvider, check: "search" },
          { kind: "model", id: selectedModel, check: "model" },
          { kind: "data", id: dataSource, check: "data" },
        ];
        for (const target of checkTargets) {
          const check = checks[target.check];
          if (check) {
            next[capabilityKey(target.kind, target.id)] =
              check.status === "success" ? "success" : "error";
          }
        }
        return next;
      });
      const checkDetails = Object.entries(checks)
        .filter(([, check]) => check.status !== "success")
        .map(
          ([name, check]) =>
            `${name}：${check.message ?? check.error_code ?? "请检查配置"}`,
        );
      setPreflightStatus(
        payload.status === "success"
          ? `预检成功：${selectedModel === "mock" ? "Mock 离线能力" : selectedModel} 当前可调用。`
          : payload.status === "partial"
            ? `预检部分成功：${failed.join("、") || "部分能力"} 需要处理。${checkDetails.join("；")}`
            : `预检失败：${failed.join("、") || "当前配置"}。${checkDetails.join("；")}`,
      );
    } catch (reason) {
      setPreflightStatus(
        reason instanceof Error ? reason.message : "能力预检失败。",
      );
    } finally {
      setIsPreflighting(false);
    }
  }

  async function replayReport(historyId: string) {
    setError("");
    const response = await fetch(
      resolveServiceURL(`ecommerce/history/${historyId}/replay`),
      {
        method: "POST",
        headers: workspaceHeaders(),
      },
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail ?? "报告回放失败");
    setResult(payload as ResearchResult);
  }

  async function compareReports() {
    if (selectedHistory.length < 2) {
      setError("请选择至少两个历史报告进行对比");
      return;
    }
    try {
      const response = await fetch(resolveServiceURL("ecommerce/compare"), {
        method: "POST",
        headers: workspaceHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ report_ids: selectedHistory }),
      });
      const payload = (await response.json()) as {
        rows: HistoryRow[];
        status: string;
      };
      if (!response.ok) throw new Error("报告对比失败");
      setComparison(payload.rows ?? []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "报告对比失败");
    }
  }

  async function previewExcel(file: File) {
    setError("");
    setExcelFile(file);
    setExcelValidation(null);
    setExcelImportStatus("");
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(resolveServiceURL("ecommerce/excel/preview"), {
      method: "POST",
      body: form,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail ?? "Excel 预览失败");
    setExcelPreview(payload as ExcelPreview);
    setExcelMapping((payload as ExcelPreview).preview.column_mapping ?? {});
  }

  async function validateExcel() {
    if (!excelFile || !result?.history_id) {
      setError("请先生成一份报告并选择 Excel 文件，再进行导入校验。");
      return;
    }
    const form = new FormData();
    form.append("file", excelFile);
    form.append("report_id", result.history_id);
    form.append("mapping_json", JSON.stringify(excelMapping));
    setExcelImportStatus("正在校验字段映射和数据质量…");
    const response = await fetch(
      resolveServiceURL("ecommerce/excel/validate"),
      {
        method: "POST",
        headers: workspaceHeaders(),
        body: form,
      },
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail ?? "Excel 校验失败");
    setExcelValidation(payload.validation ?? null);
    setExcelImportStatus(
      payload.status === "success"
        ? "校验通过，可确认导入。"
        : "校验未通过，请修正错误后重试。",
    );
  }

  async function importExcel() {
    if (!excelFile || !result?.history_id) {
      setError("请先生成报告并完成 Excel 校验。");
      return;
    }
    const form = new FormData();
    form.append("file", excelFile);
    form.append("report_id", result.history_id);
    form.append("mapping_json", JSON.stringify(excelMapping));
    form.append("confirm", "true");
    setExcelImportStatus("正在写入本地导入审计快照…");
    const response = await fetch(resolveServiceURL("ecommerce/excel/import"), {
      method: "POST",
      headers: workspaceHeaders(),
      body: form,
    });
    const payload = await response.json();
    if (!response.ok) {
      const detail =
        typeof payload.detail === "object"
          ? payload.detail.message
          : payload.detail;
      throw new Error(detail ?? "Excel 导入失败");
    }
    setExcelValidation(payload.validation ?? null);
    setExcelImportStatus(
      `导入成功：${payload.imported_count ?? 0} 行，已保存本地审计快照。`,
    );
  }

  const exportLinks = useMemo(() => {
    if (!result) return null;

    const createLink = (name: string, content: string, type: string) => ({
      href: URL.createObjectURL(new Blob([content], { type })),
      name,
    });

    return {
      json: createLink(
        `${category}-report.json`,
        JSON.stringify(result, null, 2),
        "application/json",
      ),
      markdown: createLink(
        `${category}-report.md`,
        result.report_markdown,
        "text/markdown",
      ),
      html: createLink(
        `${category}-report.html`,
        result.report_html,
        "text/html",
      ),
    };
  }, [category, result]);

  useEffect(() => {
    return () => {
      if (!exportLinks) return;
      Object.values(exportLinks).forEach((link) =>
        URL.revokeObjectURL(link.href),
      );
    };
  }, [exportLinks]);

  return (
    <main
      className={`${styles.workspace} ${styles.bentoWorkspace} px-4 py-8 text-slate-900 md:px-8 dark:text-slate-100`}
    >
      <div className={`${styles.shell} mx-auto max-w-7xl space-y-6`}>
        <header
          className={`${styles.header} flex flex-col justify-between gap-4 md:flex-row md:items-end`}
        >
          <div>
            <p className={styles.eyebrow}>DeerFlow / Product Lab</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-5xl">
              电商选品研究工作台
            </h1>
            <p className="mt-3 max-w-2xl text-sm text-slate-500 md:text-base dark:text-slate-400">
              从品类假设到证据目录，一次运行完成研究、评分、风险提示和报告导出。
            </p>
          </div>
          <div
            className={`${styles.demoBoundary} rounded-2xl px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-900`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="font-medium">演示边界</div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => void runMockDemo()}
                disabled={isRunning}
              >
                一键体验 Mock
              </Button>
            </div>
            <div className="mt-1 text-slate-500 dark:text-slate-400">
              Mock 可直接运行；真实搜索和商业数据只在用户配置授权能力后启用。
            </div>
          </div>
        </header>

        <div className={styles.trustStrip} role="note">
          <span className={styles.trustIcon} aria-hidden="true">
            ✓
          </span>
          <span>
            本工作台区分“候选证据”和“商业事实”：报告用于确定验证优先级，不直接替代销量、成本、库存或合规核验。
          </span>
          <a href="#report-summary" className={styles.trustLink}>
            查看报告边界
          </a>
        </div>

        <nav className={styles.commandBar} aria-label="研究工作台导航">
          <div className={styles.commandLabel}>
            <strong>RESEARCH COCKPIT</strong>
            <span>从配置到证据的单页工作流</span>
          </div>
          <div className={styles.commandLinks}>
            <a className={styles.commandLink} href="#research-config">
              配置
            </a>
            <a className={styles.commandLink} href="#report-summary">
              报告
            </a>
            <a className={styles.commandLink} href="#evaluation">
              评测
            </a>
            <a className={styles.commandLink} href="#history">
              历史
            </a>
            <span className={styles.modeChip}>
              <span className={styles.modeDot} aria-hidden="true" />
              {mode === "mock" ? "Mock 离线" : "Live 搜索"}
            </span>
          </div>
        </nav>

        {result && (
          <section
            className={`${styles.heroGrid} grid gap-4 lg:grid-cols-[1.3fr_1fr]`}
          >
            <Card
              className={`${styles.heroCard} border-0 text-white shadow-xl shadow-blue-950/15`}
            >
              <CardContent className="p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold tracking-[0.18em] text-emerald-300 uppercase">
                      当前最值得先验证
                    </p>
                    <h2 className="mt-2 text-2xl font-semibold">
                      {result.report.recommendations[0]?.product_name ??
                        "暂无推荐方向"}
                    </h2>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-semibold text-emerald-300">
                      {(
                        result.report.recommendations[0]?.score.total ?? 0
                      ).toFixed(1)}
                    </div>
                    <div className="text-xs text-slate-400">
                      {result.report.recommendations[0]?.price_range ??
                        "待计算"}
                    </div>
                  </div>
                </div>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
                  {result.report.executive_summary}
                </p>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl bg-white/10 p-3 text-sm">
                    <div className="text-xs text-slate-400">决策边界</div>
                    <div className="mt-1 font-medium">
                      {result.report.decision_basis}
                    </div>
                  </div>
                  <div className="rounded-xl bg-emerald-300/10 p-3 text-sm text-emerald-100">
                    <div className="text-xs text-emerald-300">
                      第一步验证动作
                    </div>
                    <div className="mt-1 font-medium">
                      {result.report.recommendations[0]?.validation_action ??
                        "补充可核验数据"}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card
              className={`${styles.timelineCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
            >
              <CardHeader>
                <CardTitle>研究进度事件</CardTitle>
                <CardDescription>
                  搜索、清洗、评分和报告生成使用同一条运行时间线。
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {(result.progress_events ?? []).map((event) => (
                  <div
                    key={event.event_id}
                    className="flex items-start gap-3 text-sm"
                  >
                    <span
                      className={`mt-1 size-2 rounded-full ${
                        event.status === "success"
                          ? "bg-emerald-500"
                          : event.status === "partial"
                            ? "bg-amber-500"
                            : event.status === "error"
                              ? "bg-red-500"
                              : "bg-blue-500"
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex justify-between gap-2">
                        <span className="font-medium">{event.message}</span>
                        <span className="text-xs text-slate-400">
                          {event.status}
                        </span>
                      </div>
                      {event.module && (
                        <div className="text-xs text-slate-500">
                          模块：{event.module}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {(!result.progress_events ||
                  result.progress_events.length === 0) && (
                  <p className="text-sm text-slate-500">
                    当前快照没有记录进度事件。
                  </p>
                )}
              </CardContent>
            </Card>
          </section>
        )}

        <section
          id="history"
          className={`${styles.utilityGrid} grid gap-6 xl:grid-cols-[1fr_1fr]`}
        >
          <Card
            className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
          >
            <CardHeader>
              <CardTitle>导入 Excel 数据</CardTitle>
              <CardDescription>
                没有商品 API 时的首选输入通道：支持
                .xlsx、.xlsm、.xls、.csv、.tsv（20 MB
                内），先预览和映射，再校验并确认导入；系统不会把预览内容自动当成商业事实。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                type="file"
                accept=".xlsx,.xlsm,.xls,.csv,.tsv"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file)
                    void previewExcel(file).catch((reason) =>
                      setError(
                        reason instanceof Error
                          ? reason.message
                          : "Excel 预览失败",
                      ),
                    );
                }}
              />
              {excelPreview && (
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                  <div className="border-b border-slate-200 p-3 text-sm dark:border-slate-800">
                    <span className="font-medium">{excelPreview.filename}</span>
                    <span className="ml-2 text-slate-500">
                      {excelPreview.preview.row_count} 行 ·{" "}
                      {excelPreview.preview.status}
                    </span>
                  </div>
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr>
                        {excelPreview.preview.columns
                          .slice(0, 8)
                          .map((column) => (
                            <th
                              key={column}
                              className="px-3 py-2 whitespace-nowrap"
                            >
                              {column}
                            </th>
                          ))}
                      </tr>
                    </thead>
                    <tbody>
                      {excelPreview.preview.preview_rows
                        .slice(0, 3)
                        .map((row, index) => (
                          <tr
                            key={index}
                            className="border-t border-slate-100 dark:border-slate-800"
                          >
                            {excelPreview.preview.columns
                              .slice(0, 8)
                              .map((column) => (
                                <td
                                  key={column}
                                  className="max-w-40 truncate px-3 py-2"
                                >
                                  {formatDisplayValue(row[column], "")}
                                </td>
                              ))}
                          </tr>
                        ))}
                    </tbody>
                  </table>
                  {excelPreview.preview.missing_required_columns.length > 0 && (
                    <p className="p-3 text-xs text-amber-700">
                      缺少必需列：
                      {excelPreview.preview.missing_required_columns.join("、")}
                    </p>
                  )}
                  <div className="space-y-3 border-t border-slate-200 p-3 dark:border-slate-800">
                    <div className="text-sm font-medium">字段映射</div>
                    <p className="text-xs text-slate-500">
                      系统已自动匹配常见中文列名；如列名不同，可在这里手动指定。
                    </p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {excelPreview.preview.required_fields.map((field) => (
                        <label
                          key={field}
                          className="text-xs text-slate-600 dark:text-slate-300"
                        >
                          {FIELD_LABELS[field] ?? field}
                          <select
                            className="border-input mt-1 h-8 w-full rounded-md border bg-transparent px-2"
                            value={excelMapping[field] ?? ""}
                            onChange={(event) =>
                              setExcelMapping((current) => ({
                                ...current,
                                [field]: event.target.value,
                              }))
                            }
                          >
                            {(
                              excelPreview.preview.mapping_options[field] ?? [
                                "",
                              ]
                            ).map((column) => (
                              <option key={`${field}-${column}`} value={column}>
                                {column || "未映射"}
                              </option>
                            ))}
                          </select>
                        </label>
                      ))}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!result?.history_id}
                        onClick={() =>
                          void validateExcel().catch((reason) =>
                            setError(
                              reason instanceof Error
                                ? reason.message
                                : "Excel 校验失败",
                            ),
                          )
                        }
                      >
                        校验当前映射
                      </Button>
                      <Button
                        size="sm"
                        disabled={
                          !result?.history_id ||
                          excelValidation?.status !== "success"
                        }
                        onClick={() =>
                          void importExcel().catch((reason) =>
                            setError(
                              reason instanceof Error
                                ? reason.message
                                : "Excel 导入失败",
                            ),
                          )
                        }
                      >
                        确认导入当前报告
                      </Button>
                      <span className="text-xs text-slate-500">
                        {result?.history_id
                          ? "当前报告已绑定"
                          : "生成报告后才能绑定导入"}
                      </span>
                    </div>
                    {excelImportStatus && (
                      <p className="text-xs text-blue-700 dark:text-blue-300">
                        {excelImportStatus}
                      </p>
                    )}
                    {excelValidation && (
                      <div className="rounded-lg bg-slate-50 p-3 text-xs dark:bg-slate-950">
                        <div className="font-medium">校验摘要</div>
                        <div className="mt-1 text-slate-500">
                          状态：{formatDisplayValue(excelValidation.status)} ·
                          行数：
                          {formatDisplayValue(excelValidation.row_count)} ·
                          已解析：
                          {formatDisplayValue(excelValidation.imported_count)}
                        </div>
                        {Array.isArray(excelValidation.errors) &&
                          excelValidation.errors.length > 0 && (
                            <ul className="mt-2 list-disc pl-5 text-red-600">
                              {(excelValidation.errors as string[])
                                .slice(0, 5)
                                .map((item) => (
                                  <li key={item}>{item}</li>
                                ))}
                            </ul>
                          )}
                        {Array.isArray(excelValidation.warnings) &&
                          excelValidation.warnings.length > 0 && (
                            <ul className="mt-2 list-disc pl-5 text-amber-700">
                              {(excelValidation.warnings as string[])
                                .slice(0, 5)
                                .map((item) => (
                                  <li key={item}>{item}</li>
                                ))}
                            </ul>
                          )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card
            className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
          >
            <CardHeader className="flex-row items-start justify-between">
              <div>
                <CardTitle>历史报告与对比</CardTitle>
                <CardDescription>
                  报告自动保存到本地 SQLite，可回放且不重复调用 API。
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void compareReports()}
              >
                对比所选
              </Button>
            </CardHeader>
            <CardContent className="space-y-2">
              {history.length === 0 && (
                <p className="text-sm text-slate-500">
                  完成一次研究后，历史报告会显示在这里。
                </p>
              )}
              {history.slice(0, 6).map((item) => (
                <div
                  key={item.history_id}
                  className={`${styles.historyRow} flex items-center gap-2 rounded-xl p-2 text-sm dark:border-slate-800`}
                >
                  <input
                    type="checkbox"
                    checked={selectedHistory.includes(item.history_id)}
                    onChange={(event) =>
                      setSelectedHistory((current) =>
                        event.target.checked
                          ? [...current, item.history_id]
                          : current.filter((id) => id !== item.history_id),
                      )
                    }
                  />
                  <button
                    className="min-w-0 flex-1 truncate text-left font-medium hover:text-blue-600"
                    onClick={() =>
                      void replayReport(item.history_id).catch((reason) =>
                        setError(
                          reason instanceof Error
                            ? reason.message
                            : "报告回放失败",
                        ),
                      )
                    }
                  >
                    {item.category}
                  </button>
                  <span className="text-xs text-slate-500">
                    {item.average_score.toFixed(1)}
                  </span>
                  <Badge variant="outline">回放</Badge>
                </div>
              ))}
              {comparison.length >= 2 && (
                <div className="mt-3 overflow-x-auto rounded-xl bg-slate-50 p-3 text-xs dark:bg-slate-950">
                  <div className="mb-2 font-medium">对比结果</div>
                  <table className="w-full text-left">
                    <thead>
                      <tr>
                        <th className="pr-4">品类</th>
                        <th className="pr-4">平均分</th>
                        <th className="pr-4">推荐数</th>
                        <th>证据数</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparison.map((item) => (
                        <tr key={item.history_id}>
                          <td className="pr-4">{item.category}</td>
                          <td className="pr-4">
                            {item.average_score.toFixed(1)}
                          </td>
                          <td className="pr-4">{item.recommendation_count}</td>
                          <td>{item.candidate_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        {evaluationSummary?.summary && (
          <section
            id="evaluation"
            className={`${styles.sectionCard} rounded-2xl p-5`}
          >
            <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
              <div>
                <div className={styles.eyebrow}>QUALITY BASELINE</div>
                <h2 className="mt-2 text-xl font-semibold">
                  50 条评测质量基线
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {evaluationSummary.config?.dataset_version ??
                    "ecommerce-eval-v1"}{" "}
                  · Mock 离线 · 外部请求 0
                </p>
              </div>
              <div className="rounded-xl bg-blue-50 px-3 py-2 text-xs text-blue-800 dark:bg-blue-950/30 dark:text-blue-200">
                人工抽检待完成：
                {evaluationSummary.human_review_pending_count ?? "-"} 条
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                [
                  "成功率",
                  formatPercent(evaluationSummary.summary.success_rate),
                ],
                [
                  "降级通过率",
                  formatPercent(
                    evaluationSummary.summary.degradation_pass_rate,
                  ),
                ],
                [
                  "Judge 均分",
                  `${(evaluationSummary.summary.judge_average_score ?? 0).toFixed(1)} / 100`,
                ],
                [
                  "P95 延迟",
                  `${(evaluationSummary.summary.latency_p95_ms ?? 0).toFixed(1)} ms`,
                ],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="rounded-xl border border-slate-200 bg-white/70 p-3 dark:border-slate-800 dark:bg-slate-950/40"
                >
                  <div className="text-xs text-slate-500">{label}</div>
                  <div className="mt-1 text-xl font-semibold">{value}</div>
                </div>
              ))}
            </div>
            <div className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(
                evaluationSummary.summary.metric_averages ?? {},
              ).map(([name, value]) => (
                <div key={name} className="text-xs">
                  <div className="flex justify-between gap-2 text-slate-600 dark:text-slate-300">
                    <span>{EVALUATION_METRIC_LABELS[name] ?? name}</span>
                    <span>{formatPercent(value)}</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800">
                    <div
                      className="h-1.5 rounded-full bg-cyan-500"
                      style={{
                        width: `${Math.max(0, Math.min(100, value * 100))}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 text-xs text-slate-500">
              本地观测事件：{observationSummary?.count ?? 0} 条；已追踪运行：
              {observationSummary?.summary?.traced_run_count ?? 0} 次； P95：
              {(observationSummary?.summary?.p95_duration_ms ?? 0).toFixed(
                1,
              )}{" "}
              ms； 可选接入外部 Langfuse，离线演示不依赖外部追踪服务。
            </div>
          </section>
        )}

        <section
          className={`${styles.mainGrid} grid gap-6 lg:grid-cols-[360px_1fr]`}
        >
          <Card
            id="research-config"
            className={`${styles.controlPanel} h-fit border-0 bg-white/90 shadow-xl shadow-blue-950/5 dark:bg-slate-900`}
          >
            <CardHeader>
              <CardTitle>研究配置</CardTitle>
              <CardDescription>
                先用 Mock 模式熟悉完整流程，再切换真实搜索。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <label className="block text-sm font-medium">
                商品品类
                <Input
                  className="mt-2"
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                />
              </label>
              <label className="block text-sm font-medium">
                批量品类（可选，每行一个）
                <textarea
                  className="border-input mt-2 min-h-20 w-full rounded-md border bg-transparent px-3 py-2 text-sm"
                  value={batchCategories}
                  onChange={(event) => setBatchCategories(event.target.value)}
                  placeholder="可折叠露营桌\n便携榨汁杯\n桌面收纳盒"
                />
              </label>
              <label className="block text-sm font-medium">
                目标市场
                <Input
                  className="mt-2"
                  value={market}
                  onChange={(event) => setMarket(event.target.value)}
                />
              </label>
              <label className="block text-sm font-medium">
                目标客群（可选）
                <Input
                  className="mt-2"
                  value={customer}
                  onChange={(event) => setCustomer(event.target.value)}
                  placeholder="按品类自动生成"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-sm font-medium">
                  最低价
                  <Input
                    className="mt-2"
                    type="number"
                    value={priceMin}
                    onChange={(event) => setPriceMin(event.target.value)}
                  />
                </label>
                <label className="text-sm font-medium">
                  最高价
                  <Input
                    className="mt-2"
                    type="number"
                    value={priceMax}
                    onChange={(event) => setPriceMax(event.target.value)}
                  />
                </label>
              </div>
              <p className="text-xs text-slate-500">{priceHint}</p>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-sm font-medium">
                  数据模式
                  <select
                    className="border-input mt-2 h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                    value={mode}
                    onChange={(event) => {
                      setMode(event.target.value as "mock" | "live");
                      clearPreflightResults();
                    }}
                  >
                    <option value="mock">Mock 演示</option>
                    <option value="live">真实搜索</option>
                  </select>
                </label>
                <label className="text-sm font-medium">
                  报告模型
                  <select
                    className="border-input mt-2 h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                    value={modelPreset}
                    onChange={(event) => selectModelPreset(event.target.value)}
                  >
                    {availableModelPresets.map((preset) => (
                      <option key={preset.id} value={preset.id}>
                        {preset.label}
                      </option>
                    ))}
                  </select>
                  <span className="mt-1 block text-xs font-normal text-slate-500">
                    选择供应商会自动填入常用 Endpoint 和模型名；Key
                    仍由你自行填写。
                  </span>
                </label>
              </div>
              <label className="block text-sm font-medium">
                搜索供应商
                <select
                  className="border-input mt-2 h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                  value={searchProvider}
                  onChange={(event) => {
                    setSearchProvider(event.target.value as SearchProviderId);
                    clearPreflightResults();
                  }}
                >
                  {(capabilities?.capabilities.search_providers ?? []).map(
                    (item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                        {item.configured ? "（已配置）" : "（未配置）"}
                      </option>
                    ),
                  )}
                </select>
              </label>
              {(searchProvider === "searxng" ||
                searchProvider === "custom_http_json") && (
                <label className="block text-sm font-medium">
                  搜索 Endpoint（可选）
                  <Input
                    className="mt-2"
                    value={searchEndpoint}
                    onChange={(event) => setSearchEndpoint(event.target.value)}
                    placeholder={
                      searchProvider === "searxng"
                        ? "http://localhost:8080/search"
                        : "https://your-search.example/search"
                    }
                  />
                  <span className="mt-1 block text-xs font-normal text-slate-500">
                    可填写本次请求的搜索 Key；不填写时使用服务端 .env 配置。
                  </span>
                </label>
              )}
              <label className="block text-sm font-medium">
                商品数据增强
                <select
                  className="border-input mt-2 h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                  value={dataSource}
                  onChange={(event) => {
                    setDataSource(event.target.value as "none" | "infoquest");
                    clearPreflightResults();
                  }}
                >
                  <option value="none">仅使用搜索摘要</option>
                  <option value="infoquest">InfoQuest 商品页增强</option>
                </select>
              </label>
              <div
                className={`${styles.apiConfigCard} min-w-0 space-y-3 rounded-lg border border-emerald-200 bg-emerald-50/60 p-3 dark:border-emerald-900 dark:bg-emerald-950/20`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">
                      用户商品 API（可选）
                    </div>
                    <p className="mt-1 text-xs font-normal text-slate-600 dark:text-slate-300">
                      没有内置真实商品 API 也可以使用：填入你有权使用的 JSON
                      商品接口，先预检，再把样品载入本次研究。
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <label className="flex items-center gap-2 text-xs font-medium text-emerald-800 dark:text-emerald-200">
                      <input
                        type="checkbox"
                        checked={productApiEnabled}
                        onChange={(event) => {
                          setProductApiEnabled(event.target.checked);
                          setProductApiStatus(
                            event.target.checked
                              ? "已启用本次商品 API 配置，请先运行预检。"
                              : "已暂停本次商品 API 配置。",
                          );
                          if (!event.target.checked) setProductApiPreview(null);
                        }}
                      />
                      <span>{productApiEnabled ? "已启用" : "未启用"}</span>
                    </label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={clearProductApi}
                    >
                      清除
                    </Button>
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
                  <label className="text-xs font-medium">
                    配置模板
                    <select
                      className="border-input mt-1 h-9 w-full rounded-md border bg-white px-2 text-sm dark:bg-slate-950"
                      value={productApiTemplate}
                      onChange={(event) =>
                        applyProductApiTemplate(event.target.value)
                      }
                    >
                      {PRODUCT_API_TEMPLATES.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="min-w-0 rounded-md bg-white/65 p-2 text-xs leading-5 text-emerald-900 dark:bg-slate-950/40 dark:text-emerald-200">
                    {PRODUCT_API_TEMPLATES.find(
                      (template) => template.id === productApiTemplate,
                    )?.description ?? "可按字段映射接入用户自有商品 API。"}
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Input
                    value={productApiProvider}
                    onChange={(event) =>
                      setProductApiProvider(event.target.value)
                    }
                    placeholder="供应商名称，例如内部商品库"
                  />
                  <Input
                    value={productApiEndpoint}
                    onChange={(event) =>
                      setProductApiEndpoint(event.target.value)
                    }
                    placeholder="https://api.example.com/products"
                    autoComplete="url"
                  />
                </div>
                <div className="grid gap-2 sm:grid-cols-3">
                  <label className="text-xs font-medium">
                    方法
                    <select
                      className="border-input mt-1 h-9 w-full rounded-md border bg-white px-2 text-sm dark:bg-slate-950"
                      value={productApiMethod}
                      onChange={(event) =>
                        setProductApiMethod(
                          event.target.value as "GET" | "POST",
                        )
                      }
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST JSON</option>
                    </select>
                  </label>
                  <label className="text-xs font-medium">
                    认证
                    <select
                      className="border-input mt-1 h-9 w-full rounded-md border bg-white px-2 text-sm dark:bg-slate-950"
                      value={productApiAuthMode}
                      onChange={(event) =>
                        setProductApiAuthMode(
                          event.target.value as "bearer" | "header" | "none",
                        )
                      }
                    >
                      <option value="bearer">Bearer Token</option>
                      <option value="header">自定义 Header</option>
                      <option value="none">无需认证</option>
                    </select>
                  </label>
                  <Input
                    type="password"
                    value={productApiKey}
                    onChange={(event) => setProductApiKey(event.target.value)}
                    placeholder={
                      productApiAuthMode === "none"
                        ? "无需填写 Key"
                        : "本次请求 API Key"
                    }
                    autoComplete="off"
                    disabled={productApiAuthMode === "none"}
                  />
                </div>
                {productApiAuthMode === "header" && (
                  <Input
                    value={productApiHeader}
                    onChange={(event) =>
                      setProductApiHeader(event.target.value)
                    }
                    placeholder="X-API-Key"
                    aria-label="商品 API 认证 Header"
                  />
                )}
                <div className="grid gap-2 sm:grid-cols-3">
                  <Input
                    value={productApiQueryParam}
                    onChange={(event) =>
                      setProductApiQueryParam(event.target.value)
                    }
                    placeholder="查询参数：q"
                    aria-label="商品 API 查询参数"
                  />
                  <Input
                    value={productApiResponsePath}
                    onChange={(event) =>
                      setProductApiResponsePath(event.target.value)
                    }
                    placeholder="响应路径：data"
                    aria-label="商品 API 响应路径"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!productApiEnabled}
                    onClick={() =>
                      void preflightProductApi().catch((reason) =>
                        setError(
                          reason instanceof Error
                            ? reason.message
                            : "商品 API 预检失败",
                        ),
                      )
                    }
                  >
                    预检并读取样品
                  </Button>
                </div>
                <div className="grid gap-2 sm:grid-cols-4">
                  {(["title", "price", "url", "sku"] as const).map((field) => (
                    <Input
                      key={field}
                      value={productApiFieldMap[field]}
                      onChange={(event) =>
                        setProductApiFieldMap((current) => ({
                          ...current,
                          [field]: event.target.value,
                        }))
                      }
                      placeholder={`${field} 字段路径`}
                      aria-label={`商品 API ${field} 字段路径`}
                    />
                  ))}
                </div>
                <p className="text-xs leading-5 text-slate-500">
                  默认期望 <code>data[]</code>；字段路径支持点号，例如{" "}
                  <code>data.items</code>。Endpoint 只允许 HTTPS，本地演示允许
                  localhost；Key 只按本次请求使用。未启用时不会参与研究请求。
                </p>
                {productApiStatus && (
                  <p className="rounded-md bg-white/70 p-2 text-xs text-emerald-800 dark:bg-slate-950/50 dark:text-emerald-200">
                    {productApiStatus}
                  </p>
                )}
                {productApiPreview?.products?.length ? (
                  <div className="space-y-2 rounded-md border border-emerald-200 bg-white/70 p-2 text-xs dark:border-emerald-900 dark:bg-slate-950/50">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span>
                        已读取 {productApiPreview.products.length}{" "}
                        条样品；商业决策门禁仍保持关闭。
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        disabled={!productApiEnabled}
                        onClick={() =>
                          void importProductApiSample().catch((reason) =>
                            setError(
                              reason instanceof Error
                                ? reason.message
                                : "商品 API 样品载入失败",
                            ),
                          )
                        }
                      >
                        载入本次研究
                      </Button>
                    </div>
                    <div className="space-y-1 text-slate-600 dark:text-slate-300">
                      {productApiPreview.products.slice(0, 3).map((product) => (
                        <div key={product.record_id} className="truncate">
                          {product.title} · {product.price ?? "价格未返回"}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
              <div className="space-y-2 rounded-lg border border-cyan-200 bg-cyan-50/60 p-3 dark:border-cyan-900 dark:bg-cyan-950/20">
                <div className="text-sm font-medium">私有知识库（可选）</div>
                <p className="text-xs font-normal text-slate-500">
                  上传商品库、供应商资料或平台规则；只作为本地候选证据参与，不会自动升级为商业事实。
                </p>
                <Input
                  type="file"
                  accept=".jsonl,.ndjson,.csv,.md,.markdown,.txt"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file)
                      void uploadKnowledgeFile(file).catch((reason) => {
                        setKnowledgeStatus(
                          reason instanceof Error
                            ? reason.message
                            : "私有知识文件上传失败",
                        );
                      });
                  }}
                />
                {knowledgeUpload && (
                  <div className="flex items-center justify-between gap-2 rounded-md bg-white/70 p-2 text-xs dark:bg-slate-950/50">
                    <span className="truncate">
                      {knowledgeUpload.filename} ·{" "}
                      {knowledgeUpload.record_count} 条记录
                    </span>
                    <button
                      type="button"
                      className="text-cyan-700 underline underline-offset-2 dark:text-cyan-300"
                      onClick={() => {
                        setKnowledgeUpload(null);
                        setKnowledgeStatus("已移除本次研究的私有知识文件");
                      }}
                    >
                      移除
                    </button>
                  </div>
                )}
                {knowledgeStatus && (
                  <p className="text-xs text-cyan-800 dark:text-cyan-200">
                    {knowledgeStatus}
                  </p>
                )}
              </div>
              <div className="space-y-3 rounded-lg border border-blue-200 bg-blue-50/60 p-3 dark:border-blue-900 dark:bg-blue-950/20">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium">
                      本次请求 API 配置（BYOK）
                    </div>
                    <div className="mt-1 text-xs font-normal text-slate-500">
                      只保存在当前页面内，提交后按请求使用，不写入历史报告或服务端配置。
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={clearBYOK}
                  >
                    清除本次配置
                  </Button>
                </div>
                <div className="flex items-start gap-2 rounded-md bg-white/70 p-2 text-xs dark:bg-slate-950/50">
                  <input
                    id="enable-model-config"
                    type="checkbox"
                    className="mt-0.5 size-4 accent-blue-600"
                    checked={modelEnabled}
                    onChange={(event) => {
                      setModelEnabled(event.target.checked);
                      clearPreflightResults();
                    }}
                  />
                  <label
                    htmlFor="enable-model-config"
                    className="cursor-pointer"
                  >
                    <span className="font-medium text-slate-700 dark:text-slate-200">
                      启用当前模型配置
                    </span>
                    <span className="mt-0.5 block text-slate-500">
                      {selectedModelPreset().description}；关闭时本次请求回退到
                      Mock。
                    </span>
                  </label>
                </div>
                {model !== "mock" && modelEnabled && (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-slate-600 dark:text-slate-300">
                      模型：{selectedModelPreset().label}
                    </div>
                    <Input
                      type="password"
                      value={modelApiKey}
                      onChange={(event) => {
                        setModelApiKey(event.target.value);
                        clearPreflightResults();
                      }}
                      placeholder={
                        model === "ollama"
                          ? "Ollama 可留空"
                          : "本次请求的模型 API Key"
                      }
                      autoComplete="off"
                    />
                    <Input
                      value={modelBaseUrl}
                      onChange={(event) => {
                        setModelBaseUrl(event.target.value);
                        clearPreflightResults();
                      }}
                      placeholder={
                        model === "ollama"
                          ? "http://localhost:11434/v1"
                          : "https://your-compatible-endpoint/v1"
                      }
                      autoComplete="off"
                    />
                    <Input
                      value={modelName}
                      onChange={(event) => {
                        setModelName(event.target.value);
                        clearPreflightResults();
                      }}
                      placeholder={
                        model === "deepseek"
                          ? "deepseek-chat（可选）"
                          : "模型名称，例如 gpt-4o-mini / qwen2.5:7b"
                      }
                      autoComplete="off"
                    />
                    <div className="text-xs font-normal text-slate-500">
                      Endpoint
                      和模型名都可以覆盖预填值；自定义入口请确认服务兼容 OpenAI
                      Chat Completions。
                    </div>
                  </div>
                )}
                {mode === "live" && (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-slate-600 dark:text-slate-300">
                      搜索：{searchProvider}
                    </div>
                    <Input
                      type="password"
                      value={searchApiKey}
                      onChange={(event) => setSearchApiKey(event.target.value)}
                      placeholder={
                        searchProvider === "searxng"
                          ? "SearXNG 可留空"
                          : "本次请求的搜索 API Key"
                      }
                      autoComplete="off"
                    />
                  </div>
                )}
                {dataSource === "infoquest" && (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-slate-600 dark:text-slate-300">
                      商品页增强：InfoQuest（固定服务）
                    </div>
                    <Input
                      type="password"
                      value={dataApiKey}
                      onChange={(event) => setDataApiKey(event.target.value)}
                      placeholder="本次请求的 InfoQuest Reader Key"
                      autoComplete="off"
                    />
                  </div>
                )}
                <div className="text-xs leading-5 text-slate-500">
                  不要把 Key 写入
                  URL、品类名称或备注。关闭页面或点击清除后，前端不再保留这组输入。
                </div>
              </div>
              <div
                className={`${styles.capabilityPanel} rounded-lg p-3 text-xs dark:border-slate-800`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">真实能力状态</span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void runPreflight()}
                    disabled={isPreflighting}
                  >
                    {isPreflighting ? "预检中…" : "预检当前能力"}
                  </Button>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-slate-500">
                  {capabilities ? (
                    requiredCapabilities().map(({ item, kind, prefix }) => {
                      const display = capabilityDisplay(item, kind);
                      return (
                        <span
                          key={`${kind}:${item.id}`}
                          className={styles.statusPill}
                          data-status={display.status}
                        >
                          {prefix} {item.label}：{display.label}
                        </span>
                      );
                    })
                  ) : (
                    <span>正在读取当前能力…</span>
                  )}
                </div>
                {preflightStatus && (
                  <div className="mt-2 text-slate-600 dark:text-slate-300">
                    {preflightStatus}
                  </div>
                )}
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={parallel}
                  onChange={(event) => setParallel(event.target.checked)}
                />
                并行搜索模块
              </label>
              <Button
                className="h-11 w-full"
                onClick={() => void runResearch()}
                disabled={isRunning || !category.trim()}
              >
                {isRunning ? "研究运行中…" : "开始生成选品报告"}
              </Button>
              <div className="space-y-2 rounded-lg border border-dashed border-blue-200 p-3 dark:border-blue-900">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={() =>
                    void runBatchResearch().catch((reason) =>
                      setError(
                        reason instanceof Error
                          ? reason.message
                          : "批量研究运行失败",
                      ),
                    )
                  }
                  disabled={isBatchRunning || !batchCategories.trim()}
                >
                  {isBatchRunning ? "批量任务运行中…" : "提交批量研究任务"}
                </Button>
                {batchTask && (
                  <div className="space-y-2 text-xs text-slate-600 dark:text-slate-300">
                    <div className="flex items-center justify-between gap-2">
                      <span>
                        批量状态：{batchTask.status} ·{" "}
                        {batchTask.counts.completed}/{batchTask.counts.total}{" "}
                        完成
                      </span>
                      {isBatchRunning ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            void cancelBatchResearch().catch((reason) =>
                              setError(
                                reason instanceof Error
                                  ? reason.message
                                  : "批量任务取消失败",
                              ),
                            )
                          }
                        >
                          取消
                        </Button>
                      ) : batchTask.counts.failed > 0 ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            void retryBatchResearch().catch((reason) =>
                              setError(
                                reason instanceof Error
                                  ? reason.message
                                  : "批量任务重试失败",
                              ),
                            )
                          }
                        >
                          重试失败项
                        </Button>
                      ) : null}
                    </div>
                    <div className="space-y-1">
                      {batchTask.items.map((item) => (
                        <div
                          key={item.item_id}
                          className="flex items-center justify-between gap-2 rounded bg-slate-50 px-2 py-1 dark:bg-slate-950"
                        >
                          <span className="truncate">{item.category}</span>
                          <span
                            className={
                              item.status === "error"
                                ? "text-red-600"
                                : item.status === "success"
                                  ? "text-emerald-600"
                                  : "text-slate-500"
                            }
                          >
                            {item.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              {isRunning && (
                <div
                  className={`${styles.runningPanel} rounded-lg p-3 text-sm dark:text-blue-200`}
                >
                  <div className="flex items-center justify-between">
                    <span>{progressStep}</span>
                    <span className="animate-pulse">●</span>
                  </div>
                  <div
                    className={`${styles.progressBar} mt-2 h-1.5 rounded-full bg-blue-100 dark:bg-blue-900`}
                  >
                    <div className="h-full w-2/3 animate-pulse rounded-full bg-blue-500" />
                  </div>
                </div>
              )}
              {error && (
                <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
                  {error}
                </p>
              )}
            </CardContent>
          </Card>

          <div
            id="report-summary"
            className={`${styles.resultsPanel ?? ""} space-y-6`}
          >
            {!result && (
              <Card
                className={`${styles.emptyState} border-dashed bg-white/70 py-16 text-center dark:bg-slate-900/60`}
              >
                <CardContent>
                  <div
                    className={`${styles.emptyGlyph} mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-blue-600 text-2xl text-white shadow-lg shadow-blue-600/30`}
                  >
                    ✦
                  </div>
                  <h2 className="text-xl font-semibold">准备开始研究</h2>
                  <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
                    点击左侧按钮，先运行一个完全离线的 Mock Demo。
                  </p>
                </CardContent>
              </Card>
            )}
            {result && (
              <>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {[
                    ["平均评分", averageScore.toFixed(1), "基于当前推荐方向"],
                    [
                      "推荐方向",
                      String(result.report.recommendations.length),
                      "可继续验证",
                    ],
                    [
                      "候选证据",
                      String(result.candidate_catalog.candidates.length),
                      "仅候选，不是商业事实",
                    ],
                    [
                      "运行耗时",
                      `${(result.metrics.latency_ms ?? 0).toFixed(0)} ms`,
                      result.metrics.quality_level ?? "已完成",
                    ],
                  ].map(([label, value, note]) => (
                    <Card
                      key={label}
                      className={`${styles.metricCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                    >
                      <CardContent className="p-5">
                        <div className="text-sm text-slate-500">{label}</div>
                        <div className="mt-2 text-3xl font-semibold">
                          {value}
                        </div>
                        <div className="mt-1 text-xs text-slate-400">
                          {note}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                <nav className={styles.reportSectionNav} aria-label="报告分区">
                  {(
                    [
                      ["summary", "摘要", "report-section-summary"],
                      ["market", "市场", "report-section-market"],
                      ["competitive", "竞品", "report-section-competitive"],
                      ["customer", "人群", "report-section-customer"],
                      ["risk", "风险", "report-section-risk"],
                      ["action", "行动", "report-section-action"],
                      ["evidence", "证据", "report-section-evidence"],
                    ] as const
                  ).map(([section, label, target]) => (
                    <a
                      key={section}
                      href={`#${target}`}
                      className={`${styles.reportSectionLink} ${activeReportSection === section ? styles.reportSectionLinkActive : ""}`}
                      onClick={() => setActiveReportSection(section)}
                    >
                      {label}
                    </a>
                  ))}
                </nav>

                <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
                  <Card
                    className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                  >
                    <CardHeader>
                      <CardTitle>研究过程与 Agent 状态</CardTitle>
                      <CardDescription>
                        展示从任务拆解到 Reviewer
                        门禁的执行链路；单个模块失败时会保留降级说明。
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-2 sm:grid-cols-2">
                      {(result.agent_plan ?? []).map((agent) => {
                        const detail = result.agent_results?.[agent] ?? {};
                        const status = detail.status ?? "unknown";
                        return (
                          <div
                            key={agent}
                            className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-950/50"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium">
                                {AGENT_LABELS[agent] ?? agent}
                              </span>
                              <Badge
                                variant={
                                  status === "success" ? "default" : "secondary"
                                }
                              >
                                {humanizeStatus(status)}
                              </Badge>
                            </div>
                            <div className="mt-2 text-xs text-slate-500">
                              证据 {detail.evidence_ids?.length ?? 0} 条 · 尝试{" "}
                              {detail.attempts ?? 1} 次
                            </div>
                            {detail.error_kind && (
                              <div className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                                降级原因：{detail.error_kind}
                              </div>
                            )}
                          </div>
                        );
                      })}
                      {(result.agent_plan ?? []).length === 0 && (
                        <p className="text-sm text-slate-500">
                          当前报告未记录 Agent 状态。
                        </p>
                      )}
                    </CardContent>
                  </Card>

                  <Card
                    className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                  >
                    <CardHeader>
                      <CardTitle>证据边界审计</CardTitle>
                      <CardDescription>
                        把私有知识、引用完整性和商业核验状态分开呈现。
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span>私有知识库</span>
                        <Badge
                          variant={
                            result.knowledge_status === "success"
                              ? "default"
                              : "secondary"
                          }
                        >
                          {result.knowledge_status === "success"
                            ? `命中 ${formatDisplayValue(result.knowledge_details?.hit_count, "0")} 条`
                            : result.knowledge_status === "no_hit"
                              ? "已检索但未命中"
                              : result.knowledge_status === "not_used"
                                ? "未启用"
                                : humanizeStatus(result.knowledge_status)}
                        </Badge>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span>引用完整性</span>
                        <Badge
                          variant={
                            result.citation_validation?.complete
                              ? "default"
                              : "secondary"
                          }
                        >
                          {result.citation_validation?.complete
                            ? "通过"
                            : "待补齐"}
                        </Badge>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span>商业核验</span>
                        <Badge variant="secondary">
                          {result.verification_validation?.complete
                            ? "已通过结构校验"
                            : "需人工核验"}
                        </Badge>
                      </div>
                      <p className="text-xs leading-5 text-slate-500">
                        候选证据不会自动变成销量、成本、库存或合规事实；最终采购判断仍需人工核验。
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {result.quality_audit && (
                  <Card
                    id="report-section-quality"
                    className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                  >
                    <CardHeader>
                      <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
                        <div>
                          <CardTitle>研究质量审计</CardTitle>
                          <CardDescription>
                            把接口完成、来源质量和商业决策门禁分层展示；审计结论不会把候选数据包装成商业事实。
                          </CardDescription>
                        </div>
                        <Badge
                          variant={
                            result.quality_audit.status === "commercial_ready"
                              ? "default"
                              : "secondary"
                          }
                        >
                          {qualityStatusLabel(result.quality_audit.status)}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid gap-2 sm:grid-cols-3">
                        {Object.entries(result.quality_audit.gates ?? {}).map(
                          ([name, passed]) => (
                            <div
                              key={name}
                              className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-slate-950/60"
                            >
                              <span>{QUALITY_GATE_LABELS[name] ?? name}</span>
                              <Badge variant={passed ? "default" : "secondary"}>
                                {passed ? "通过" : "待补齐"}
                              </Badge>
                            </div>
                          ),
                        )}
                      </div>
                      <div className="grid gap-3 text-xs text-slate-600 sm:grid-cols-2 lg:grid-cols-4 dark:text-slate-300">
                        <span>
                          来源结果{" "}
                          {result.quality_audit.search?.total_result_count ?? 0}{" "}
                          条
                        </span>
                        <span>
                          大陆相关率{" "}
                          {formatPercent(
                            result.quality_audit.search
                              ?.mainland_relevance_rate,
                          )}
                        </span>
                        <span>
                          价格覆盖率{" "}
                          {formatPercent(
                            result.quality_audit.search
                              ?.competitor_price_coverage,
                          )}
                        </span>
                        <span>
                          报告告警{" "}
                          {result.quality_audit.report?.warning_count ?? 0} 条
                        </span>
                      </div>
                      {(result.quality_audit.blocking_reasons ?? []).length >
                        0 && (
                        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-200">
                          <div className="font-medium">当前阻断原因</div>
                          <ul className="mt-1 list-disc space-y-1 pl-4">
                            {(result.quality_audit.blocking_reasons ?? [])
                              .slice(0, 4)
                              .map((reason) => (
                                <li key={reason}>{reason}</li>
                              ))}
                          </ul>
                        </div>
                      )}
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                        <span>
                          Trace ID：{result.trace_id ?? "本地运行未记录"}
                        </span>
                        <span>
                          模型成本状态：
                          {result.quality_audit.model?.cost_status ?? "不可用"}
                        </span>
                        <span>
                          本地 P95：
                          {(
                            observationSummary?.summary?.p95_duration_ms ?? 0
                          ).toFixed(1)}{" "}
                          ms
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                )}

                <Card
                  className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                >
                  <CardHeader>
                    <CardTitle>趋势与价格分布</CardTitle>
                    <CardDescription>
                      用当前报告中的推荐评分和价格锚点做快速比较；图表只表达候选证据，不替代商业核验。
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-5 lg:grid-cols-2">
                    <section
                      className="min-w-0"
                      aria-labelledby="score-trend-title"
                    >
                      <h3
                        id="score-trend-title"
                        className="mb-2 text-sm font-medium"
                      >
                        推荐方向得分趋势
                      </h3>
                      <MiniLineChart points={reportChartData.trend} />
                    </section>
                    <section
                      className="min-w-0"
                      aria-labelledby="price-distribution-title"
                    >
                      <h3
                        id="price-distribution-title"
                        className="mb-2 text-sm font-medium"
                      >
                        价格分布
                      </h3>
                      <PriceDistributionChart prices={reportChartData.prices} />
                    </section>
                  </CardContent>
                </Card>

                <Card
                  id="report-section-market"
                  className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                >
                  <CardHeader>
                    <CardTitle>一、市场趋势</CardTitle>
                    <CardDescription>
                      需求信号、方向和增长线索；所有结论都保留证据关联，不代表真实市场规模。
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3 md:grid-cols-3">
                    {(result.report.trends ?? []).map((trend) => (
                      <div
                        key={trend.name}
                        className="rounded-xl border border-slate-200 p-3 dark:border-slate-800"
                      >
                        <div className="font-medium">{trend.name}</div>
                        <div className="mt-1 text-sm text-slate-500">
                          {trend.rationale}
                        </div>
                        <div className="mt-2 text-xs text-blue-600">
                          {trend.direction} · 需求{" "}
                          {trend.demand_score.toFixed(0)} · 增长{" "}
                          {(trend.growth_rate * 100).toFixed(0)}%
                        </div>
                      </div>
                    ))}
                    {(result.report.trends ?? []).length === 0 && (
                      <p className="text-sm text-slate-500">暂无趋势信号。</p>
                    )}
                  </CardContent>
                </Card>

                <Card
                  id="report-section-competitive"
                  className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                >
                  <CardHeader>
                    <CardTitle>二、竞品与价格</CardTitle>
                    <CardDescription>
                      展示竞品定位、价格锚点和竞争差异，价格仅作为候选研究依据。
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3 md:grid-cols-3">
                    {(result.report.competitors ?? []).map((competitor) => (
                      <div
                        key={competitor.name}
                        className="rounded-xl border border-slate-200 p-3 dark:border-slate-800"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{competitor.name}</span>
                          <span className="text-sm font-semibold text-blue-600">
                            ¥{competitor.price.toFixed(0)}
                          </span>
                        </div>
                        <div className="mt-2 text-sm text-slate-500">
                          {competitor.positioning}
                        </div>
                        <div className="mt-2 text-xs text-slate-400">
                          优势：
                          {(competitor.strengths ?? []).join("、") || "待补齐"}
                          ；短板：
                          {(competitor.weaknesses ?? []).join("、") || "待补齐"}
                        </div>
                      </div>
                    ))}
                    {(result.report.competitors ?? []).length === 0 && (
                      <p className="text-sm text-slate-500">暂无竞品数据。</p>
                    )}
                  </CardContent>
                </Card>

                <Card
                  id="report-section-customer"
                  className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                >
                  <CardHeader>
                    <CardTitle>三、目标人群匹配</CardTitle>
                    <CardDescription>
                      把客群、需求、痛点和购买触发因素放在同一处，便于设计验证问卷或试销素材。
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3 md:grid-cols-2">
                    {(result.report.customer_profiles ?? []).map((profile) => (
                      <div
                        key={profile.segment}
                        className="rounded-xl border border-slate-200 p-3 dark:border-slate-800"
                      >
                        <div className="font-medium">{profile.segment}</div>
                        <div className="mt-2 text-sm text-slate-500">
                          需求：{(profile.needs ?? []).join("、") || "待补齐"}
                        </div>
                        <div className="mt-1 text-sm text-slate-500">
                          痛点：
                          {(profile.pain_points ?? []).join("、") || "待补齐"}
                        </div>
                        <div className="mt-1 text-xs text-blue-600">
                          触发：
                          {(profile.buying_triggers ?? []).join("、") ||
                            "待补齐"}
                        </div>
                      </div>
                    ))}
                    {(result.report.customer_profiles ?? []).length === 0 && (
                      <p className="text-sm text-slate-500">暂无客群画像。</p>
                    )}
                  </CardContent>
                </Card>

                <Card
                  id="report-section-risk"
                  className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                >
                  <CardHeader>
                    <CardTitle>四、风险与进入壁垒</CardTitle>
                    <CardDescription>
                      同时展示机会、风险和缓解动作，明确当前仍处于验证阶段。
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3 md:grid-cols-2">
                    {(result.report.opportunities_risks ?? []).map(
                      (item, index) => (
                        <div
                          key={`${item.opportunity}-${index}`}
                          className="rounded-xl border border-amber-200 bg-amber-50/60 p-3 dark:border-amber-900/60 dark:bg-amber-950/20"
                        >
                          <div className="font-medium">
                            机会 {item.opportunity_score.toFixed(0)}：
                            {item.opportunity}
                          </div>
                          <div className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                            风险 {item.risk_score.toFixed(0)}：
                            {(item.risks ?? []).join("；") || "待补齐"}
                          </div>
                          <div className="mt-2 text-xs text-amber-800 dark:text-amber-200">
                            缓解：
                            {(item.mitigations ?? []).join("；") || "待补齐"}
                          </div>
                        </div>
                      ),
                    )}
                    {(result.report.opportunities_risks ?? []).length === 0 && (
                      <p className="text-sm text-slate-500">暂无风险评估。</p>
                    )}
                  </CardContent>
                </Card>

                <Card
                  id="report-section-summary"
                  className={`${styles.reportCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                >
                  <CardHeader className="flex-row items-start justify-between">
                    <div>
                      <CardTitle>研究结论</CardTitle>
                      <CardDescription>
                        {result.report.executive_summary}
                      </CardDescription>
                      <p className="mt-3 text-sm text-slate-500">
                        {result.report.decision_basis}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Badge variant="outline">
                        决策：{humanizeDecision(result.report.decision_status)}
                      </Badge>
                      <Badge variant="secondary">
                        搜索：{humanizeStatus(result.search_status)}
                      </Badge>
                      <Badge variant="secondary">
                        模型：{humanizeStatus(result.model_status)}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-3 dark:bg-slate-950/60">
                      <div>
                        <div className="text-xs tracking-wide text-slate-500 uppercase">
                          当前判断
                        </div>
                        <div className="mt-1 font-semibold">
                          {humanizeDecision(result.report.decision_status)}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs tracking-wide text-slate-500 uppercase">
                          推荐均分
                        </div>
                        <div className="mt-1 font-semibold text-blue-600">
                          {averageScore.toFixed(1)} / 100
                        </div>
                      </div>
                      <div>
                        <div className="text-xs tracking-wide text-slate-500 uppercase">
                          证据边界
                        </div>
                        <div className="mt-1 font-semibold">
                          {result.report.evidence.length} 条报告证据
                        </div>
                      </div>
                    </div>
                    <div
                      id="report-section-action"
                      className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
                    >
                      <div className="text-base font-semibold">
                        五、推荐方向与验证动作
                      </div>
                      <div className="font-medium">建议的下一步</div>
                      <div className="mt-1 text-xs opacity-80">
                        这些动作用于补齐商业验证，不代表已经确认真实销量、库存或利润。
                      </div>
                      <ol className="mt-2 list-decimal space-y-1 pl-5">
                        {result.report.next_actions.map((action) => (
                          <li key={action}>{action}</li>
                        ))}
                      </ol>
                    </div>
                    <div className="rounded-xl border border-slate-200 p-3 text-xs dark:border-slate-800">
                      <div className="font-medium">报告质量门禁</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(
                          result.report_quality_gates ??
                            result.metrics.report_quality_gates ??
                            {},
                        ).map(([name, passed]) => (
                          <Badge
                            key={name}
                            variant={passed ? "default" : "secondary"}
                          >
                            {name}: {passed ? "通过" : "待补齐"}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    {result.report.recommendations.map((item, index) => (
                      <div
                        key={item.product_name}
                        className={`${styles.recommendationCard} rounded-2xl p-4 dark:border-slate-800`}
                      >
                        <div className="flex flex-col justify-between gap-2 md:flex-row">
                          <div>
                            <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase">
                              {index === 0
                                ? "首选验证方向"
                                : `备选方向 ${String(index).padStart(2, "0")}`}
                            </div>
                            <h3 className="mt-1 text-lg font-semibold">
                              {item.product_name}
                            </h3>
                            <p className="mt-1 text-sm text-slate-500">
                              {item.positioning}
                            </p>
                            <p className="mt-2 text-xs text-slate-400">
                              价格依据：{item.price_basis}
                            </p>
                          </div>
                          <div className="text-left md:text-right">
                            <div className="text-3xl font-semibold text-blue-600">
                              {item.score.total.toFixed(1)}
                            </div>
                            <div className="text-xs text-slate-400">
                              {item.price_range}
                            </div>
                          </div>
                        </div>
                        <div className="mt-4 grid gap-2 sm:grid-cols-5">
                          {scoreItems(item).map(([label, value]) => (
                            <div key={label}>
                              <div className="mb-1 flex justify-between text-xs text-slate-500">
                                <span>{label}</span>
                                <span>{value.toFixed(0)}</span>
                              </div>
                              <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-800">
                                <div
                                  className="h-1.5 rounded-full bg-blue-500"
                                  style={{ width: `${value}%` }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                        <p className="mt-4 text-sm leading-6 text-slate-600 dark:text-slate-300">
                          {item.rationale}
                        </p>
                        {item.evidence_ids && item.evidence_ids.length > 0 && (
                          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                            <span className="font-medium text-slate-600 dark:text-slate-300">
                              关联证据：
                            </span>
                            {item.evidence_ids.slice(0, 5).map((evidenceId) => (
                              <a
                                key={evidenceId}
                                href={`#evidence-${evidenceId}`}
                                className="rounded-full bg-blue-50 px-2 py-1 text-blue-700 underline-offset-2 hover:underline dark:bg-blue-950/30 dark:text-blue-300"
                              >
                                {evidenceId.slice(0, 12)}
                              </a>
                            ))}
                          </div>
                        )}
                        <div
                          className={`${styles.validationCard} mt-3 rounded-lg p-3 text-sm`}
                        >
                          <div className={styles.validationTitle}>验证卡片</div>
                          <div className={`${styles.validationRow} mt-1`}>
                            <strong>动作：</strong>
                            {item.validation_action}
                          </div>
                          <div className={`${styles.validationRow} mt-1`}>
                            <strong>成功阈值：</strong>
                            {item.validation_threshold}
                          </div>
                          <div className={`${styles.validationRow} mt-1`}>
                            <strong>需要补齐：</strong>
                            {item.validation_data_needed.join("、")}
                          </div>
                          <div className={`${styles.validationRow} mt-1`}>
                            <strong>未达标处理：</strong>
                            {item.validation_failure_action}
                          </div>
                          <span className={styles.validationNote}>
                            {item.score_note}
                          </span>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                {searchModules.length > 0 && (
                  <Card
                    className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                  >
                    <CardHeader>
                      <CardTitle>搜索过程与来源质量</CardTitle>
                      <CardDescription>
                        展示每个研究模块的状态、清洗数量、价格提取和来源分级。
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-3 sm:grid-cols-2">
                      {searchModules.map(([module, details]) => (
                        <div
                          key={module}
                          className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-800"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{module}</span>
                            <Badge
                              variant={
                                details.status === "success"
                                  ? "default"
                                  : "secondary"
                              }
                            >
                              {humanizeStatus(
                                formatDisplayValue(details.status, "unknown"),
                              )}
                            </Badge>
                          </div>
                          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-500">
                            <span>
                              结果：
                              {formatDisplayValue(
                                details.result_count ??
                                  details.cleaned_result_count ??
                                  "-",
                              )}
                            </span>
                            <span>
                              价格：
                              {formatDisplayValue(details.priced_result_count)}
                            </span>
                            <span>
                              去重：
                              {formatDisplayValue(
                                details.cleaned_duplicate_count,
                                "0",
                              )}
                            </span>
                            <span>
                              低分过滤：
                              {formatDisplayValue(
                                details.filtered_low_score_count,
                                "0",
                              )}
                            </span>
                            <span>
                              来源质量：
                              {details.source_quality_score == null
                                ? "-"
                                : Number(details.source_quality_score).toFixed(
                                    2,
                                  )}
                            </span>
                            <span className="col-span-2">
                              价格锚点：
                              {Array.isArray(details.price_anchor_values) &&
                              details.price_anchor_values.length
                                ? details.price_anchor_values
                                    .map(
                                      (price) => `¥${Number(price).toFixed(0)}`,
                                    )
                                    .join(" / ")
                                : "未提取到明确价格"}
                            </span>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                <div
                  id="report-section-evidence"
                  className="grid gap-6 xl:grid-cols-2"
                >
                  <Card
                    className={`${styles.sectionCard} border-0 bg-white shadow-sm dark:bg-slate-900`}
                  >
                    <CardHeader>
                      <CardTitle>候选证据</CardTitle>
                      <CardDescription>
                        按来源质量和证据覆盖排序；不会自动升级为商业事实。
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {result.candidate_catalog.candidates
                        .slice(0, 8)
                        .map((candidate) => (
                          <div
                            key={candidate.candidate_id}
                            className={`${styles.evidenceItem} rounded-xl p-3 dark:border-slate-800`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="font-medium">
                                {candidate.title}
                              </div>
                              <Badge>
                                {candidate.candidate_rank_score.toFixed(2)}
                              </Badge>
                            </div>
                            <div className="mt-2 text-xs text-slate-500">
                              {candidate.source_domain} ·{" "}
                              {candidate.source_quality_category} ·{" "}
                              {candidate.modules.join(" / ")}
                            </div>
                          </div>
                        ))}
                    </CardContent>
                  </Card>
                  <Card className="border-0 bg-white shadow-sm dark:bg-slate-900">
                    <CardHeader>
                      <CardTitle>研究证据与导出</CardTitle>
                      <CardDescription>
                        报告指纹：{result.report_fingerprint.slice(0, 16)}…
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {result.report.evidence.slice(0, 6).map((item) => (
                        <div
                          key={item.evidence_id}
                          id={`evidence-${item.evidence_id}`}
                          className={`${styles.evidenceItem} rounded-xl p-3 dark:border-slate-800`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <a
                              href={item.source}
                              target="_blank"
                              rel="noreferrer"
                              className="font-medium hover:text-blue-700 hover:underline dark:hover:text-blue-300"
                            >
                              {item.title}
                            </a>
                            <Badge variant="outline">
                              {sourceTypeLabel(item.source_type)}
                            </Badge>
                          </div>
                          <div className="mt-1 line-clamp-2 text-xs text-slate-500">
                            {item.summary}
                          </div>
                          <details className="mt-2 text-xs text-slate-500">
                            <summary className="cursor-pointer font-medium text-blue-700 dark:text-blue-300">
                              查看证据边界与来源信息
                            </summary>
                            <div className="mt-2 space-y-1 rounded-lg bg-slate-50 p-2 dark:bg-slate-950">
                              <div>证据 ID：{item.evidence_id}</div>
                              <div>
                                置信度：{(item.confidence * 100).toFixed(0)}%
                              </div>
                              <div>
                                检索时间：{formatDateTime(item.retrieved_at)}
                              </div>
                              <div>
                                支持模块：
                                {item.supports?.join("、") ?? "未记录"}
                              </div>
                              <div className="break-all">
                                来源：{item.source}
                              </div>
                            </div>
                          </details>
                        </div>
                      ))}
                      <div className="flex flex-wrap gap-2 pt-2">
                        <a
                          className="border-input bg-background hover:bg-accent hover:text-accent-foreground inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium shadow-sm transition-colors"
                          download={exportLinks?.json.name}
                          href={exportLinks?.json.href}
                        >
                          下载 JSON
                        </a>
                        <a
                          className="border-input bg-background hover:bg-accent hover:text-accent-foreground inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium shadow-sm transition-colors"
                          download={exportLinks?.markdown.name}
                          href={exportLinks?.markdown.href}
                        >
                          下载 Markdown
                        </a>
                        <a
                          className="border-input bg-background hover:bg-accent hover:text-accent-foreground inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium shadow-sm transition-colors"
                          download={exportLinks?.html.name}
                          href={exportLinks?.html.href}
                        >
                          下载 HTML
                        </a>
                      </div>
                    </CardContent>
                  </Card>
                </div>
                {result.report.warnings.length > 0 && (
                  <Card className="border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30">
                    <CardHeader>
                      <CardTitle>运行提示</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800 dark:text-amber-200">
                        {result.report.warnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
