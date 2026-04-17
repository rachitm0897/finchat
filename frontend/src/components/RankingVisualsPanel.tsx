
import { useState } from "react";
import { getPeerRanking } from "../api/api";
import { formatAnyNumber } from "../utils/display";

export default function RankingVisualsPanel() {
  const [input, setInput] = useState("AAPL,MSFT,GOOGL");
  const [payload, setPayload] = useState<any>(null);

  const load = async () => {
    const tickers = input.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean);
    if (tickers.length < 2) return;
    try {
      const res = await getPeerRanking(tickers);
      setPayload(res.data.data);
    } catch (err) {
      console.error("Ranking visuals failed:", err);
      setPayload(null);
    }
  };

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>RANKING BARS</h3>
          <div className="panel-subtitle">Visual order by composite score</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={load}>LOAD</button>
      </div>
      <div className="inline-filter-row">
        <input value={input} onChange={(e) => setInput(e.target.value.toUpperCase())} placeholder="AAPL,MSFT,GOOGL" />
      </div>
      {!payload ? (
        <div className="empty-state">No ranking data loaded.</div>
      ) : (
        <div className="rank-bar-stack">
          {(payload.overall_ranking || []).map((row: any) => (
            <div key={row.ticker} className="rank-bar-row rank-bar-row-extended">
              <span className="rank-index">#{row.overall_rank}</span>
              <span className="rank-bar-label">{row.ticker}</span>
              <div className="rank-bar-track">
                <div className="rank-bar-fill" style={{ width: `${Math.min(Number(row.composite_score || 0) * 18, 100)}%` }} />
              </div>
              <span className="rank-bar-value">{formatAnyNumber(row.composite_score)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
