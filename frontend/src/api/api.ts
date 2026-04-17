import axios from "axios";

const API = axios.create({
  baseURL: "http://localhost:8000/api/",
  headers: {
    "Content-Type": "application/json",
  },
});

// ---- COMPANY ----
export const searchCompany = (q: string) =>
  API.get(`companies/search/?q=${encodeURIComponent(q)}`);

export const listAvailableCompanies = (limit = 100) =>
  API.get(`companies/search/?q=&limit=${limit}`);

export const getCompanyDetail = (ticker: string) =>
  API.get(`companies/${ticker}/`);

export const ingestCompany = (ticker: string, asyncMode = true) =>
  API.post("companies/ingest/", {
    ticker,
    ingest_statements: true,
    async_mode: asyncMode,
  });

export const computeAnalytics = (ticker: string, asyncMode = true) =>
  API.post("analytics/compute/", {
    ticker,
    calc_version: "v1",
    async_mode: asyncMode,
  });

export const getMetrics = (ticker: string, latestOnly = true, limit = 100) =>
  API.get(
    `companies/${ticker}/metrics/?latest_only=${latestOnly ? "true" : "false"}&limit=${limit}&period_type=annual`
  );

export const compareCompanies = (tickers: string[]) =>
  API.post("companies/compare/", {
    tickers,
    period_type: "annual",
  });

export const getAnalysisSummary = (ticker: string) =>
  API.get(`companies/${ticker}/analysis-summary/`);

export const getPeerRanking = (tickers: string[]) =>
  API.post("companies/peer-rank/", { tickers });

export const getScenarioAnalysis = (ticker: string, years = 3) =>
  API.post("companies/scenario-analysis/", { ticker, years });

export const getCompanyTrends = (ticker: string, periodType = "annual", limit = 8) =>
  API.get(`companies/${ticker}/trends/?period_type=${periodType}&limit=${limit}`);

export const getDCFValuation = (ticker: string) =>
  API.post("companies/dcf-valuation/", { ticker });

export const getComparisonVisuals = (tickers: string[]) =>
  API.post("companies/compare-visuals/", { tickers, period_type: "annual" });

export const exportCompanyReportUrl = (ticker: string, format: "json" | "markdown" = "json") =>
  `http://localhost:8000/api/reports/company/${ticker}/export/?format=${format}`;


// ---- BACKTESTING ----
// export const runBacktest = (payload: {
//   ticker: string;
//   strategy_type: "sma_crossover" | "support_resistance_rsi_volume";
//   start_date: string;
//   end_date: string;
//   initial_capital: number;
//   position_size: number;
//   commission_bps: number;
//   resolution?: "D";
//   async_mode?: boolean;
//   use_stored_data?: boolean;
//   benchmark_symbol?: string;
//   config_json:
//     | {
//         short_window: number;
//         long_window: number;
//       }
//     | {
//         support_window: number;
//         resistance_window: number;
//         rsi_window: number;
//         rsi_buy: number;
//         rsi_sell: number;
//         volume_window: number;
//         volume_multiplier: number;
//         buy_tolerance_pct: number;
//         sell_tolerance_pct: number;
//       };
// }) =>
//   API.post("backtests/run/", {
//     resolution: "D",
//     async_mode: true,
//     use_stored_data: true,
//     benchmark_symbol: "",
//     ...payload,
//   });

export const listBacktestRuns = (ticker = "", limit = 20) =>
  API.get(`backtests/runs/?ticker=${encodeURIComponent(ticker)}&limit=${limit}`);

export const getBacktestRun = (runId: string) =>
  API.get(`backtests/runs/${runId}/`);

// ---- PORTFOLIO ----

export const getPortfolioActions = (query: string, limit = 10) =>
  API.post("portfolio/actions/", { query, limit });

// ---- JOBS ----
export const getJobStatus = (jobId: string) =>
  API.get(`jobs/${jobId}/`);

// ---- CHAT SESSIONS ----
export const createChatSession = (title = "", context_json: Record<string, unknown> = {}) =>
  API.post("chat/sessions/", {
    title,
    context_json,
    user_identifier: "",
  });

export const listChatSessions = () =>
  API.get("chat/sessions/");

export const getChatSession = (sessionId: string) =>
  API.get(`chat/sessions/${sessionId}/`);

export const getChatMessages = (sessionId: string) =>
  API.get(`chat/sessions/${sessionId}/messages/`);

export const sendChatMessage = (sessionId: string, content: string) =>
  API.post(`chat/sessions/${sessionId}/messages/`, {
    content,
  });

// ---- ONE SHOT CHAT ----
export const chatQuery = (message: string) =>
  API.post("chat/query/", { message });

// ---- TICKER UNIVERSE SEARCH ----
export const searchTickerUniverse = (q: string, limit = 10) =>
  API.get(`ticker-universe/search/?q=${encodeURIComponent(q)}&limit=${limit}`);

export const runBacktest = (payload: {
  ticker: string;
  strategy_type:
    | "sma_crossover"
    | "support_resistance_rsi_volume"
    | "momentum"
    | "mean_reversion"
    | "portfolio_momentum";
  start_date: string;
  end_date: string;
  initial_capital: number;
  position_size: number;
  commission_bps: number;
  resolution?: "D";
  async_mode?: boolean;
  use_stored_data?: boolean;
  benchmark_symbol?: string;
  config_json: Record<string, unknown>;
}) =>
  API.post("backtests/run/", {
    resolution: "D",
    async_mode: true,
    use_stored_data: true,
    benchmark_symbol: "",
    ...payload,
  });

export const getSystemMetrics = () => API.get("system/metrics/");

export default API;