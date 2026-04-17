import { useEffect, useMemo, useState } from "react";
import { getMetrics } from "../api/api";
import type { MetricRow } from "../types";
import { pickChartMetrics } from "../utils/metrics";

type Props = {
  ticker: string;
  refreshKey: number;
};

function MiniBarChart({ metrics }: { metrics: MetricRow[] }) {
  const numericValues = metrics
    .map((m) => Number(m.metric_value))
    .filter((v) => !Number.isNaN(v));

  const maxValue = numericValues.length ? Math.max(...numericValues.map((v) => Math.abs(v))) : 1;

  return (
    <svg width="100%" height="260" viewBox="0 0 800 260" className="chart-svg">
      {metrics.map((metric, index) => {
        const value = Number(metric.metric_value);
        const safeValue = Number.isNaN(value) ? 0 : value;
        const barHeight = (Math.abs(safeValue) / maxValue) * 140;
        const x = 40 + index * 120;
        const y = 180 - barHeight;
        const color = safeValue >= 0 ? "#22c55e" : "#ef4444";

        return (
          <g key={metric.metric_code}>
            <line x1={0} y1={180} x2={800} y2={180} stroke="#475569" />
            <rect x={x} y={y} width={56} height={barHeight} fill={color} rx={4} />
            <text x={x + 28} y={y - 8} textAnchor="middle" fill="#e2e8f0" fontSize="12">
              {Number.isNaN(value) ? "N/A" : value.toFixed(2)}
            </text>
            <text x={x + 28} y={210} textAnchor="middle" fill="#94a3b8" fontSize="11">
              {metric.metric_code.slice(0, 12)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function ChartPanel({ ticker, refreshKey }: Props) {
  const [metrics, setMetrics] = useState<MetricRow[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchMetrics = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    try {
      const res = await getMetrics(ticker, true, 100);
      setMetrics(res.data.data.results || []);
    } catch (err) {
      console.error("Chart metrics fetch failed:", err);
      setMetrics([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchMetrics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker, refreshKey]);

  const chartMetrics = useMemo(() => pickChartMetrics(metrics), [metrics]);

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Chart Layer</h2>
        <button onClick={fetchMetrics} disabled={loading}>
          Refresh Charts
        </button>
      </div>

      {chartMetrics.length === 0 ? (
        <div className="empty-state">No chartable metrics available.</div>
      ) : (
        <MiniBarChart metrics={chartMetrics} />
      )}
    </div>
  );
}