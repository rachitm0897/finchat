
import { useState } from "react";
import { getPeerRanking } from "../api/api";
import { formatAnyNumber } from "../utils/display";

export default function PeerRankingPanel() {
  const [input, setInput] = useState("AAPL,MSFT,GOOGL");
  const [ranking, setRanking] = useState<any>(null);

  const handleLoad = async () => {
    const tickers = input.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean);
    if (tickers.length < 2) return;
    try {
      const res = await getPeerRanking(tickers);
      setRanking(res.data.data);
    } catch (err) {
      console.error("Peer ranking failed:", err);
      setRanking(null);
    }
  };

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>PEER RANKING</h3>
          <div className="panel-subtitle">Composite relative rank summary</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={handleLoad}>RANK</button>
      </div>
      <div className="inline-filter-row">
        <input value={input} onChange={(e) => setInput(e.target.value.toUpperCase())} placeholder="AAPL,MSFT,GOOGL" />
      </div>
      {!ranking ? (
        <div className="empty-state">No peer ranking loaded.</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Ticker</th>
                <th>Company</th>
                <th>Composite Score</th>
              </tr>
            </thead>
            <tbody>
              {(ranking.overall_ranking || []).map((row: any) => (
                <tr key={row.ticker}>
                  <td className="cell-emphasis">{formatAnyNumber(row.overall_rank)}</td>
                  <td>{row.ticker}</td>
                  <td>{row.company_name}</td>
                  <td>{formatAnyNumber(row.composite_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
