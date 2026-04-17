export type ChatMessage = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
};

export type JobStatus = {
  id: string;
  status: "pending" | "running" | "success" | "failed" | "cancelled";
  job_type: string;
  celery_task_id?: string;
  request_payload_json?: Record<string, unknown>;
  result_payload_json?: Record<string, unknown>;
  error_payload_json?: Record<string, unknown>;
  started_at?: string | null;
  finished_at?: string | null;
};

export type MetricRow = {
  id?: string;
  metric_code: string;
  metric_name: string;
  metric_value: string | null;
  unit: string;
  as_of_date?: string | null;
  period_type?: string | null;
  notes?: string;
};

export type CompanySummary = {
  id: string;
  ticker: string;
  finnhub_symbol?: string;
  name: string;
  country?: string;
  currency_code?: string;
  exchange?: string;
  primary_exchange?: string;
  ipo_date?: string | null;
  market_identifier_code?: string;
  logo_url?: string;
  web_url?: string;
  industry?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
};

export type TickerUniverseResult = {
  ticker: string;
  symbol?: string;
  name: string;
  description?: string;
  exchange?: string;
  type?: string;
  currency?: string;
  country?: string;
  is_ingested?: boolean;
};

export type ChatSession = {
  id: string;
  title: string;
  status: string;
  context_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  companies: Array<{
    id: string;
    ticker: string;
    name: string;
  }>;
};

export type ComparisonMetric = {
  metric_code: string;
  metric_name: string;
  metric_value: string | null;
  unit: string;
  as_of_date: string | null;
  period_type: string | null;
  calculation_version: string | null;
};

export type ComparisonRow = {
  company: CompanySummary;
  metrics: ComparisonMetric[];
};

export type BacktestMetricMap = {
  total_return_pct: number;
  buy_hold_return_pct?: number;
  alpha_vs_buy_hold_pct?: number;
  annualized_return_pct: number;
  volatility_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  exposure_pct: number;
  total_trades: number;
  trade_win_rate_pct?: number;
  profit_factor?: number | null;
  start_equity: number;
  end_equity: number;
  bars_used: number;
};

export type BacktestCurvePoint = {
  date: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  equity?: number;
  position?: number;
  drawdown_pct?: number;
  event?: string;
  reason?: string;
  short_ma?: number | null;
  long_ma?: number | null;
  rsi?: number | null;
  support?: number | null;
  resistance?: number | null;
  avg_volume?: number | null;
  volume?: number | null;
  volume_spike?: boolean | null;
};

export type BacktestTrade = {
  date: string;
  action: string;
  price: number;
  position_after: number;
  estimated_cost_pct: number;
  reason?: string;
  entry_date?: string;
  trade_return_pct?: number;
};

export type BacktestRun = {
  id: string;
  company: {
    id: string;
    ticker: string;
    name: string;
  };
  name: string;
  strategy_type: string;
  resolution: string;
  benchmark_symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: string;
  position_size: string;
  commission_bps: string;
  status: "pending" | "running" | "success" | "failed";
  request_payload_json: Record<string, unknown>;
  summary_json: Record<string, unknown>;
  error_payload_json: Record<string, unknown>;
  result?: {
    id: string;
    metrics_json: BacktestMetricMap;
    equity_curve_json: BacktestCurvePoint[];
    drawdown_curve_json: BacktestCurvePoint[];
    signal_curve_json: BacktestCurvePoint[];
    trades_json: BacktestTrade[];
    monthly_return_table_json: Array<{ month: string; return_pct: number }>;
  } | null;
  created_at: string;
  updated_at: string;
};