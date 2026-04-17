
import { useEffect, useMemo, useState } from "react";
import { getAnalysisSummary } from "../api/api";
import { formatAnyNumber } from "../utils/display";

type Props = {
  ticker: string;
  refreshKey: number;
};

export default function AnalysisSummaryPanel({ ticker, refreshKey }: Props) {
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const loadSummary = async () => {
    setLoading(true);
    try {
      const res = await getAnalysisSummary(ticker);
      setSummary(res.data.data);
    } catch (err) {
      console.error("Failed to load analysis summary:", err);
      setSummary(null);
    }
    setLoading(false);
  };

  useEffect(() => {
    void loadSummary();
  }, [ticker, refreshKey]);

  const keyMetrics = useMemo(() => {
    const rows = Object.entries(summary?.key_metrics || {});
    return rows.slice(0, 8);
  }, [summary]);

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>SUMMARY SIGNALS</h3>
          <div className="panel-subtitle">Condensed qualitative flags for {ticker}</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={loadSummary} disabled={loading}>
          REFRESH
        </button>
      </div>

      {!summary ? (
        <div className="empty-state">No analysis summary available.</div>
      ) : (
        <div className="summary-layout">
          <div className="signal-column">
            <div className="signal-column-title">STRENGTHS</div>
            {(summary.strengths || []).length ? (
              summary.strengths.map((item: string, idx: number) => (
                <div key={idx} className="signal-row positive">{item}</div>
              ))
            ) : (
              <div className="empty-state compact">No strong positive signals flagged.</div>
            )}
          </div>

          <div className="signal-column">
            <div className="signal-column-title">WEAKNESSES</div>
            {(summary.weaknesses || []).length ? (
              summary.weaknesses.map((item: string, idx: number) => (
                <div key={idx} className="signal-row negative">{item}</div>
              ))
            ) : (
              <div className="empty-state compact">No strong negative signals flagged.</div>
            )}
          </div>

          <div className="signal-column metrics-column">
            <div className="signal-column-title">KEY METRICS</div>
            <div className="mini-stat-grid">
              {keyMetrics.length === 0 ? (
                <div className="empty-state compact">No key metrics returned.</div>
              ) : (
                keyMetrics.map(([label, value]) => (
                  <div key={label} className="mini-stat-row">
                    <span>{label}</span>
                    <strong>{formatAnyNumber(value)}</strong>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
