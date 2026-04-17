
import { useEffect, useState } from "react";
import { getCompanyTrends } from "../api/api";
import { formatAnyNumber } from "../utils/display";

type Props = {
  ticker: string;
  refreshKey: number;
};

function toPoints(series: Array<{ value: string | null }>, width: number, height: number) {
  const nums = series.map((x) => (x.value == null ? null : Number(x.value)));
  const valid = nums.filter((x): x is number => x !== null && !Number.isNaN(x));
  if (valid.length === 0) return "";
  const min = Math.min(...valid);
  const max = Math.max(...valid);
  const range = max - min || 1;
  return nums
    .map((val, i) => {
      const x = (i / Math.max(series.length - 1, 1)) * width;
      const y = val == null || Number.isNaN(val) ? height : height - ((val - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");
}

function SparkPanel({
  title,
  series,
}: {
  title: string;
  series: Array<{ period_end_date: string | null; value: string | null }>;
}) {
  const width = 420;
  const height = 120;
  const points = toPoints(series, width, height);
  const lastValue = series[series.length - 1]?.value;

  return (
    <div className="chart-panel terminal-grid-bg">
      <div className="chart-panel-header">
        <div className="chart-panel-title">{title}</div>
        <div className="chart-panel-value">{formatAnyNumber(lastValue)}</div>
      </div>
      <svg viewBox={`0 0 ${width} ${height + 8}`} className="chart-svg dense">
        <polyline fill="none" stroke="currentColor" strokeWidth="2" points={points} />
      </svg>
      <div className="chart-axis-row">
        {(series || []).slice(-4).map((row, idx) => (
          <span key={`${title}-${idx}`}>{row.period_end_date || "-"}</span>
        ))}
      </div>
    </div>
  );
}

export default function TrendChartsPanel({ ticker, refreshKey }: Props) {
  const [payload, setPayload] = useState<any>(null);

  const load = async () => {
    try {
      const res = await getCompanyTrends(ticker, "annual", 8);
      setPayload(res.data.data);
    } catch (err) {
      console.error("Trend charts failed:", err);
      setPayload(null);
    }
  };

  useEffect(() => {
    void load();
  }, [ticker, refreshKey]);

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>OPERATING TRENDS</h3>
          <div className="panel-subtitle">Annual trend lines used in the current analytics payload</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={load}>
          REFRESH
        </button>
      </div>

      {!payload ? (
        <div className="empty-state">No trend data available.</div>
      ) : (
        <div className="trend-grid">
          <SparkPanel title="Revenue" series={payload.series.revenue || []} />
          <SparkPanel title="Revenue Growth YoY" series={payload.series.growth_revenue_yoy || []} />
          <SparkPanel title="Gross Margin" series={payload.series.gross_margin || []} />
          <SparkPanel title="Net Margin" series={payload.series.net_margin || []} />
          <SparkPanel title="Free Cash Flow" series={payload.series.free_cash_flow || []} />
          <SparkPanel title="FCF Margin" series={payload.series.fcf_margin || []} />
        </div>
      )}
    </section>
  );
}
