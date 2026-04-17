import { useEffect, useState } from "react";
import { getBacktestRun, getJobStatus, listBacktestRuns, runBacktest } from "../api/api";
import type { BacktestRun } from "../types";

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
      const res = await listBacktestRuns(ticker, 10);
      setRuns(res.data?.data?.results || []);
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
              tickers: form.portfolio_tickers.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean),
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
        let done = false;
        while (!done) {
          const status = await getJobStatus(jobId);
          const currentStatus = status.data?.data?.status;

          if (currentStatus === "success") {
            done = true;
            if (runId) {
              await loadRunDetail(runId);
            }
            await loadRuns();
          } else if (currentStatus === "failed" || currentStatus === "cancelled") {
            done = true;
          } else {
            await new Promise((r) => setTimeout(r, 2000));
          }
        }
      }
    } catch (err) {
      console.error("Backtest run failed:", err);
    }

    setLoading(false);
  };

  const handleAddToComparison = () => {
    if (!selectedRun) return;

    setComparisonRuns((prev) => {
      const exists = prev.some((run) => run.id === selectedRun.id);
      if (exists) return prev;
      return [...prev, selectedRun];
    });
  };

  return (
    <div className="panel">
      <h2>Backtesting</h2>

      <div className="form">
        <select
          value={strategyType}
          onChange={(e) => setStrategyType(e.target.value as StrategyType)}
        >
          <option value="sma_crossover">SMA</option>
          <option value="support_resistance_rsi_volume">SR + RSI</option>
          <option value="momentum">Momentum</option>
          <option value="mean_reversion">Mean Reversion</option>
          <option value="portfolio_momentum">Portfolio Momentum</option>
        </select>

        <input
          type="date"
          value={form.start_date}
          onChange={(e) => setForm((p) => ({ ...p, start_date: e.target.value }))}
        />

        <input
          type="date"
          value={form.end_date}
          onChange={(e) => setForm((p) => ({ ...p, end_date: e.target.value }))}
        />

        <button onClick={handleRun}>{loading ? "Running..." : "Run"}</button>
      </div>

      <div className="row" style={{ gap: "16px", marginBottom: "12px", flexWrap: "wrap" }}>
        <label style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={showRSI}
            onChange={() => setShowRSI((prev) => !prev)}
          />
          RSI Panel
        </label>

        <label style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={showSignals}
            onChange={() => setShowSignals((prev) => !prev)}
          />
          Signal Markers
        </label>

        <label style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={showComparison}
            onChange={() => setShowComparison((prev) => !prev)}
          />
          Multi-Strategy Comparison
        </label>

        <button type="button" onClick={handleAddToComparison}>
          Add Current Run to Comparison
        </button>
      </div>

      <div>
        {runs.map((r) => (
          <button key={r.id} onClick={() => loadRunDetail(r.id)}>
            {r.strategy_type}
          </button>
        ))}
      </div>

      <div className="chart-grid">
        <div className="chart-card">
          <h3>Price / OHLC View</h3>
          <CandlestickChart data={selectedRun?.result?.signal_curve_json || []} />
        </div>

        <div className="chart-card">
          <h3>Equity vs Price</h3>
          <EquityChart data={selectedRun?.result?.equity_curve_json || []} />
        </div>

        <div className="chart-card">
          <h3>Drawdown Curve</h3>
          <DrawdownChart data={selectedRun?.result?.drawdown_curve_json || []} />
        </div>

        {showRSI && (
          <div className="chart-card">
            <h3>RSI Panel</h3>
            <RSIChart data={selectedRun?.result?.signal_curve_json || []} />
          </div>
        )}

        {showSignals && (
          <div className="chart-card">
            <h3>Signal Overlay</h3>
            <SignalChart data={selectedRun?.result?.signal_curve_json || []} />
          </div>
        )}

        {showComparison && comparisonRuns.length > 1 && (
          <div className="chart-card">
            <h3>Multi-Strategy Comparison</h3>
            <MultiStrategyChart
              datasets={comparisonRuns.map((run) => ({
                name: `${run.strategy_type}-${run.id.slice(0, 6)}`,
                data: run.result?.equity_curve_json || [],
              }))}
            />
          </div>
        )}
      </div>
    </div>
  );
}