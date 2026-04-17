import { useEffect, useMemo, useState } from "react";
import { getBacktestRun, getJobStatus, listBacktestRuns, runBacktest } from "../api/api";
import type { BacktestMetricMap, BacktestRun } from "../types";

import CandlestickChart from "./charts/CandlestickChart";
import DrawdownChart from "./charts/DrawdownChart";
import EquityChart from "./charts/EquityChart";
import MultiStrategyChart from "./charts/MultiStrategyChart";
import RSIChart from "./charts/RSIChart";
import SignalChart from "./charts/SignalChart";

type Props = { ticker: string };

type StrategyType =
  | "sma_crossover"
  | "support_resistance_rsi_volume"
  | "momentum"
  | "mean_reversion"
  | "portfolio_momentum";

const STRATEGY_LABELS: Record<StrategyType, string> = {
  sma_crossover: "SMA CROSSOVER",
  support_resistance_rsi_volume: "SR + RSI + VOLUME",
  momentum: "MOMENTUM",
  mean_reversion: "MEAN REVERSION",
  portfolio_momentum: "PORTFOLIO MOMENTUM",
};

function metricOrDash(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (Number.isFinite(num)) return num.toFixed(2);
  return String(value);
}

export default function BacktestingPanel({ ticker }: Props) {
  const [strategyType, setStrategyType] = useState<StrategyType>("sma_crossover");

  const [form, setForm] = useState({
    start_date: "2020-01-01",
    end_date: "2024-01-01",
    initial_capital: 10000,
    position_size: 1,
    commission_bps: 10,
    short_window: 20,
    long_window: 50,
    support_window: 20,
    resistance_window: 20,
    rsi_window: 14,
    rsi_buy: 35,
    rsi_sell: 65,
    volume_window: 20,
    volume_multiplier: 1.5,
    buy_tolerance_pct: 2.0,
    sell_tolerance_pct: 2.0,
    lookback_window: 90,
    z_entry: 1.5,
    z_exit: 0.25,
    rebalance_days: 21,
    top_n: 3,
    portfolio_tickers: "AAPL,MSFT,NVDA,GOOGL",
  });

  const [loading, setLoading] = useState(false);
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null);
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [showRSI, setShowRSI] = useState(true);
  const [showSignals, setShowSignals] = useState(true);
  const [showComparison, setShowComparison] = useState(false);
  const [comparisonRuns, setComparisonRuns] = useState<BacktestRun[]>([]);

  const loadRuns = async () => {
    try {
      const res = await listBacktestRuns(ticker, 15);
      const nextRuns = res.data?.data?.results || [];
      setRuns(nextRuns);

      if (!selectedRun && nextRuns.length > 0) {
        setSelectedRun(nextRuns[0]);
      }
    } catch (err) {
      console.error("Failed to load backtest runs:", err);
      setRuns([]);
    }
  };

  useEffect(() => {
    void loadRuns();
  }, [ticker]);

  const loadRunDetail = async (id: string) => {
    try {
      const res = await getBacktestRun(id);
      setSelectedRun(res.data?.data || null);
    } catch (err) {
      console.error("Failed to load backtest run detail:", err);
      setSelectedRun(null);
    }
  };

  const handleRun = async () => {
    if (!ticker.trim()) return;

    setLoading(true);

    try {
      const config_json =
        strategyType === "sma_crossover"
          ? {
              short_window: Number(form.short_window),
              long_window: Number(form.long_window),
            }
          : strategyType === "support_resistance_rsi_volume"
          ? {
              support_window: Number(form.support_window),
              resistance_window: Number(form.resistance_window),
              rsi_window: Number(form.rsi_window),
              rsi_buy: Number(form.rsi_buy),
              rsi_sell: Number(form.rsi_sell),
              volume_window: Number(form.volume_window),
              volume_multiplier: Number(form.volume_multiplier),
              buy_tolerance_pct: Number(form.buy_tolerance_pct),
              sell_tolerance_pct: Number(form.sell_tolerance_pct),
            }
          : strategyType === "momentum"
          ? {
              lookback_window: Number(form.lookback_window),
              top_n: Number(form.top_n),
            }
          : strategyType === "mean_reversion"
          ? {
              lookback_window: Number(form.lookback_window),
              z_entry: Number(form.z_entry),
              z_exit: Number(form.z_exit),
            }
          : {
              tickers: form.portfolio_tickers
                .split(",")
                .map((item) => item.trim().toUpperCase())
                .filter(Boolean),
              lookback_window: Number(form.lookback_window),
              rebalance_days: Number(form.rebalance_days),
              top_n: Number(form.top_n),
            };

      const payload = {
        ticker,
        strategy_type: strategyType,
        start_date: form.start_date,
        end_date: form.end_date,
        initial_capital: Number(form.initial_capital),
        position_size: Number(form.position_size),
        commission_bps: Number(form.commission_bps),
        config_json,
      };

      const res = await runBacktest(payload);
      const jobId = res.data?.data?.job_id;
      const runId = res.data?.data?.backtest_run_id;

      if (jobId) {
        let complete = false;

        while (!complete) {
          const status = await getJobStatus(jobId);
          const currentStatus = status.data?.data?.status;

          if (currentStatus === "success") {
            complete = true;
            if (runId) {
              await loadRunDetail(runId);
            }
            await loadRuns();
          } else if (currentStatus === "failed" || currentStatus === "cancelled") {
            complete = true;
          } else {
            await new Promise((r) => setTimeout(r, 2000));
          }
        }
      }
    } catch (err) {
      console.error("Backtest run failed:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddToComparison = () => {
    if (!selectedRun) return;

    setComparisonRuns((prev) => {
      const exists = prev.some((run) => run.id === selectedRun.id);
      if (exists) return prev;
      return [...prev, selectedRun];
    });
  };

  const metrics = (selectedRun?.result?.metrics_json || {}) as Partial<BacktestMetricMap>;

  const metricCards = useMemo(
    () => [
      { label: "TOTAL RETURN %", value: metrics.total_return_pct },
      { label: "ANNUALIZED RETURN %", value: metrics.annualized_return_pct },
      { label: "SHARPE", value: metrics.sharpe_ratio },
      { label: "MAX DRAWDOWN %", value: metrics.max_drawdown_pct },
      { label: "WIN RATE %", value: metrics.trade_win_rate_pct },
      { label: "TRADES", value: metrics.total_trades },
    ],
    [metrics]
  );

  const signalData = selectedRun?.result?.signal_curve_json || [];
  const equityData = selectedRun?.result?.equity_curve_json || [];
  const drawdownData = selectedRun?.result?.drawdown_curve_json || [];

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>BACKTESTING</h3>
          <div className="panel-subtitle">
            Strategy execution, run history, chart diagnostics, comparison view
          </div>
        </div>
        <div className="toolbar-actions">
          <button type="button" className="app-button app-button-ghost" onClick={handleAddToComparison}>
            ADD TO COMPARE
          </button>
          <button type="button" className="app-button" onClick={handleRun} disabled={loading}>
            {loading ? "RUNNING" : "RUN BACKTEST"}
          </button>
        </div>
      </div>

      <div className="backtest-shell">
        <div className="backtest-config">
          <div className="toolbar-label">STRATEGY CONFIG</div>

          <div className="backtest-form-grid">
            <div className="form-field">
              <label>Strategy</label>
              <select
                value={strategyType}
                onChange={(e) => setStrategyType(e.target.value as StrategyType)}
              >
                <option value="sma_crossover">SMA CROSSOVER</option>
                <option value="support_resistance_rsi_volume">SR + RSI + VOLUME</option>
                <option value="momentum">MOMENTUM</option>
                <option value="mean_reversion">MEAN REVERSION</option>
                <option value="portfolio_momentum">PORTFOLIO MOMENTUM</option>
              </select>
            </div>

            <div className="form-field">
              <label>Start Date</label>
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm((p) => ({ ...p, start_date: e.target.value }))}
              />
            </div>

            <div className="form-field">
              <label>End Date</label>
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => setForm((p) => ({ ...p, end_date: e.target.value }))}
              />
            </div>

            <div className="form-field">
              <label>Initial Capital</label>
              <input
                type="number"
                value={form.initial_capital}
                onChange={(e) => setForm((p) => ({ ...p, initial_capital: Number(e.target.value) }))}
              />
            </div>

            <div className="form-field">
              <label>Position Size</label>
              <input
                type="number"
                step="0.1"
                value={form.position_size}
                onChange={(e) => setForm((p) => ({ ...p, position_size: Number(e.target.value) }))}
              />
            </div>

            <div className="form-field">
              <label>Commission Bps</label>
              <input
                type="number"
                value={form.commission_bps}
                onChange={(e) => setForm((p) => ({ ...p, commission_bps: Number(e.target.value) }))}
              />
            </div>

            {strategyType === "sma_crossover" && (
              <>
                <div className="form-field">
                  <label>Short Window</label>
                  <input
                    type="number"
                    value={form.short_window}
                    onChange={(e) => setForm((p) => ({ ...p, short_window: Number(e.target.value) }))}
                  />
                </div>
                <div className="form-field">
                  <label>Long Window</label>
                  <input
                    type="number"
                    value={form.long_window}
                    onChange={(e) => setForm((p) => ({ ...p, long_window: Number(e.target.value) }))}
                  />
                </div>
              </>
            )}

            {strategyType === "support_resistance_rsi_volume" && (
              <>
                <div className="form-field">
                  <label>Support Window</label>
                  <input
                    type="number"
                    value={form.support_window}
                    onChange={(e) => setForm((p) => ({ ...p, support_window: Number(e.target.value) }))}
                  />
                </div>
                <div className="form-field">
                  <label>Resistance Window</label>
                  <input
                    type="number"
                    value={form.resistance_window}
                    onChange={(e) => setForm((p) => ({ ...p, resistance_window: Number(e.target.value) }))}
                  />
                </div>
                <div className="form-field">
                  <label>RSI Window</label>
                  <input
                    type="number"
                    value={form.rsi_window}
                    onChange={(e) => setForm((p) => ({ ...p, rsi_window: Number(e.target.value) }))}
                  />
                </div>
                <div className="form-field">
                  <label>RSI Buy</label>
                  <input
                    type="number"
                    value={form.rsi_buy}
                    onChange={(e) => setForm((p) => ({ ...p, rsi_buy: Number(e.target.value) }))}
                  />
                </div>
                <div className="form-field">
                  <label>RSI Sell</label>
                  <input
                    type="number"
                    value={form.rsi_sell}
                    onChange={(e) => setForm((p) => ({ ...p, rsi_sell: Number(e.target.value) }))}
                  />
                </div>
                <div className="form-field">
                  <label>Volume Window</label>
                  <input
                    type="number"
                    value={form.volume_window}
                    onChange={(e) => setForm((p) => ({ ...p, volume_window: Number(e.target.value) }))}
                  />
                </div>
              </>
            )}

            {(strategyType === "momentum" || strategyType === "mean_reversion" || strategyType === "portfolio_momentum") && (
              <div className="form-field">
                <label>Lookback Window</label>
                <input
                  type="number"
                  value={form.lookback_window}
                  onChange={(e) => setForm((p) => ({ ...p, lookback_window: Number(e.target.value) }))}
                />
              </div>
            )}

            {strategyType === "mean_reversion" && (
              <>
                <div className="form-field">
                  <label>Z Entry</label>
                  <input
                    type="number"
                    step="0.1"
                    value={form.z_entry}
                    onChange={(e) => setForm((p) => ({ ...p, z_entry: Number(e.target.value) }))}
                  />
                </div>
                <div className="form-field">
                  <label>Z Exit</label>
                  <input
                    type="number"
                    step="0.1"
                    value={form.z_exit}
                    onChange={(e) => setForm((p) => ({ ...p, z_exit: Number(e.target.value) }))}
                  />
                </div>
              </>
            )}

            {strategyType === "portfolio_momentum" && (
              <>
                <div className="form-field">
                  <label>Portfolio Tickers</label>
                  <input
                    type="text"
                    value={form.portfolio_tickers}
                    onChange={(e) => setForm((p) => ({ ...p, portfolio_tickers: e.target.value.toUpperCase() }))}
                  />
                </div>
                <div className="form-field">
                  <label>Rebalance Days</label>
                  <input
                    type="number"
                    value={form.rebalance_days}
                    onChange={(e) => setForm((p) => ({ ...p, rebalance_days: Number(e.target.value) }))}
                  />
                </div>
                <div className="form-field">
                  <label>Top N</label>
                  <input
                    type="number"
                    value={form.top_n}
                    onChange={(e) => setForm((p) => ({ ...p, top_n: Number(e.target.value) }))}
                  />
                </div>
              </>
            )}
          </div>

          <div className="backtest-toggles">
            <label><input type="checkbox" checked={showRSI} onChange={() => setShowRSI((p) => !p)} /> RSI PANEL</label>
            <label><input type="checkbox" checked={showSignals} onChange={() => setShowSignals((p) => !p)} /> SIGNALS</label>
            <label><input type="checkbox" checked={showComparison} onChange={() => setShowComparison((p) => !p)} /> MULTI-RUN COMPARISON</label>
          </div>
        </div>

        <div className="backtest-sidebar">
          <div className="toolbar-label">RUN HISTORY</div>
          <div className="backtest-run-list">
            {runs.length === 0 ? (
              <div className="empty-state compact">No backtest runs available.</div>
            ) : (
              runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  className={`backtest-run-item ${selectedRun?.id === run.id ? "active" : ""}`}
                  onClick={() => void loadRunDetail(run.id)}
                >
                  <div className="backtest-run-title">
                    {STRATEGY_LABELS[(run.strategy_type as StrategyType) || "sma_crossover"] || run.strategy_type}
                  </div>
                  <div className="backtest-run-meta">
                    <span>{run.start_date}</span>
                    <span>{run.end_date}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="metric-grid compact-grid">
        {metricCards.map((item) => (
          <div key={item.label} className="metric-card">
            <div className="metric-name">{item.label}</div>
            <div className="metric-value">{metricOrDash(item.value)}</div>
          </div>
        ))}
      </div>

      <div className="chart-grid chart-grid-analytics">
        <div className="chart-card">
          <div className="chart-card-title">PRICE STRUCTURE</div>
          <CandlestickChart data={signalData} />
        </div>

        <div className="chart-card">
          <div className="chart-card-title">EQUITY VS PRICE</div>
          <EquityChart data={equityData} />
        </div>

        <div className="chart-card">
          <div className="chart-card-title">DRAWDOWN</div>
          <DrawdownChart data={drawdownData} />
        </div>

        {showRSI && (
          <div className="chart-card">
            <div className="chart-card-title">RSI</div>
            <RSIChart data={signalData} />
          </div>
        )}

        {showSignals && (
          <div className="chart-card">
            <div className="chart-card-title">SIGNAL OVERLAY</div>
            <SignalChart data={signalData} />
          </div>
        )}

        {showComparison && comparisonRuns.length > 1 && (
          <div className="chart-card chart-card-wide">
            <div className="chart-card-title">MULTI-STRATEGY EQUITY</div>
            <MultiStrategyChart
              datasets={comparisonRuns.map((run) => ({
                name: `${run.strategy_type}-${run.id.slice(0, 6)}`,
                data: run.result?.equity_curve_json || [],
              }))}
            />
          </div>
        )}
      </div>
    </section>
  );
}