
import { useState } from "react";
import { getPortfolioActions } from "../api/api";
import { formatAnyNumber } from "../utils/display";

export default function PortfolioActionsPanel() {
  const [query, setQuery] = useState("Find me high growth, low debt companies with good quality score");
  const [payload, setPayload] = useState<any>(null);

  const run = async () => {
    try {
      const res = await getPortfolioActions(query, 10);
      setPayload(res.data.data);
    } catch (err) {
      console.error("Portfolio action failed:", err);
      setPayload(null);
    }
  };

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>PORTFOLIO QUERY TOOL</h3>
          <div className="panel-subtitle">Natural language request translated into ranking output</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={run}>RUN</button>
      </div>
      <div className="inline-filter-row">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find me high growth, low debt companies..." />
      </div>
      {!payload ? (
        <div className="empty-state">No portfolio action result loaded.</div>
      ) : (
        <>
          <div className="note-box">{JSON.stringify(payload.action_plan, null, 2)}</div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Ticker</th>
                  <th>Company</th>
                  <th>Ranking Metric</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {(payload.results || []).map((row: any) => (
                  <tr key={`${row.rank}-${row.ticker}`}>
                    <td>{formatAnyNumber(row.rank)}</td>
                    <td>{row.ticker}</td>
                    <td>{row.company_name}</td>
                    <td>{row.ranking_metric}</td>
                    <td>{formatAnyNumber(row.ranking_metric_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
