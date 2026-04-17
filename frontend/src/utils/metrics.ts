
import type { MetricRow } from "../types";
import { formatAnyNumber, asNumber } from "./display";

export const GROUP_ORDER = [
  "valuation",
  "profitability",
  "growth",
  "risk",
  "leverage",
  "liquidity",
  "efficiency",
  "cashflow",
  "trend",
  "summary",
];

export function metricGroup(metricCode: string) {
  const prefix = metricCode.split("_")[0];
  return prefix || "other";
}

export function formatMetricValue(value: string | null, unit: string) {
  if (value == null) return "N/A";
  const num = asNumber(value);
  if (num === null) return value;
  if (unit === "flag") return num === 1 ? "Yes" : "No";
  if (unit === "pct") return `${formatAnyNumber(num)}%`;
  return formatAnyNumber(num);
}

export function groupMetrics(metrics: MetricRow[]) {
  const map: Record<string, MetricRow[]> = {};
  for (const row of metrics) {
    const group = metricGroup(row.metric_code);
    if (!map[group]) map[group] = [];
    map[group].push(row);
  }
  return map;
}

export function pickChartMetrics(metrics: MetricRow[]) {
  const preferred = [
    "profitability_net_margin",
    "growth_revenue_yoy",
    "cashflow_fcf_margin",
    "liquidity_current_ratio",
    "leverage_debt_to_equity",
    "summary_quality_score",
  ];

  const result: MetricRow[] = [];
  for (const code of preferred) {
    const found = metrics.find((m) => m.metric_code === code);
    if (found) result.push(found);
  }
  return result;
}
