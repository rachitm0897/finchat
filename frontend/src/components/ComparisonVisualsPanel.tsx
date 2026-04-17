
import { useState } from "react";
import { getComparisonVisuals } from "../api/api";
import { formatAnyNumber } from "../utils/display";

function VisualCard({ title, rows }: { title: string; rows: Array<{ ticker: string; metric_value: string | null }> }) {
  const values = rows.map((row) => Number(row.metric_value || 0));
  const max = Math.max(...values, 1);

  return (
    <div className="panel-subblock terminal-grid-bg">
      <div className="panel-subblock-title">{title}</div>
      <div className="rank-bar-stack">
        {rows.map((row) => (
          <div key={`${title}-${row.ticker}`} className="rank-bar-row">
            <span className="rank-bar-label">{row.ticker}</span>
            <div className="rank-bar-track">
              <div className="rank-bar-fill" style={{ width: `${(Number(row.metric_value || 0) / max) * 100}%` }} />
            </div>
            <span className="rank-bar-value">{formatAnyNumber(row.metric_value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ComparisonVisualsPanel() {
  const [input, setInput] = useState("AAPL,MSFT,GOOGL");
  const [payload, setPayload] = useState<any>(null);

  const load = async () => {
    const tickers = input.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean);
    if (tickers.length < 2) return;
    try {
      const res = await getComparisonVisuals(tickers);
      setPayload(res.data.data);
    } catch (err) {
      console.error("Comparison visuals failed:", err);
      setPayload(null);
    }
  };

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>RELATIVE VISUALS</h3>
          <div className="panel-subtitle">Bar view across selected metrics</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={load}>LOAD</button>
      </div>
      <div className="inline-filter-row">
        <input value={input} onChange={(e) => setInput(e.target.value.toUpperCase())} placeholder="AAPL,MSFT,GOOGL" />
      </div>
      {!payload ? (
        <div className="empty-state">No comparison visuals loaded.</div>
      ) : (
        <div className="subblock-grid">
          {(payload.visuals || []).map((visual: any) => (
            <VisualCard key={visual.metric_code} title={visual.metric_code} rows={visual.rows || []} />
          ))}
        </div>
      )}
    </section>
  );
}
