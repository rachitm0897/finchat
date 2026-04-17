import { useState } from "react";
import { compareCompanies } from "../api/api";
import type { ComparisonRow } from "../types";
import { formatMetricValue } from "../utils/metrics";

type Props = {
  ticker: string;
};

export default function ComparisonPanel({ ticker }: Props) {
  const [input, setInput] = useState(`${ticker},MSFT,GOOGL`);
  const [rows, setRows] = useState<ComparisonRow[]>([]);
  const [metricCodes, setMetricCodes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const handleCompare = async () => {
    const tickers = input.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean);
    if (tickers.length < 2) {
      alert("Enter at least two tickers");
      return;
    }
    setLoading(true);
    try {
      const res = await compareCompanies(tickers);
      const payload = res.data.data;
      setRows(payload.results || []);
      setMetricCodes(payload.metric_codes || []);
    } catch (err) {
      console.error("Comparison failed:", err);
      setRows([]);
      setMetricCodes([]);
    }
    setLoading(false);
  };

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>Peer Comparison Table</h3>
          <div className="panel-subtitle">Cross-company readout on a shared computed metric set</div>
        </div>
        <button type="button" className="app-button" onClick={handleCompare} disabled={loading}>
          LOAD COMPARISON
        </button>
      </div>

      <div className="inline-filter-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          placeholder="AAPL,MSFT,GOOGL"
        />
      </div>

      {rows.length === 0 ? (
        <div className="empty-state">No comparison loaded.</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table comparison-table">
            <thead>
              <tr>
                <th>Metric</th>
                {rows.map((row) => (
                  <th key={row.company.id}>
                    <div className="cell-title">{row.company.ticker}</div>
                    <div className="cell-subtitle">{row.company.name}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metricCodes.map((metricCode) => {
                const label = rows[0]?.metrics.find((m) => m.metric_code === metricCode)?.metric_name || metricCode;
                return (
                  <tr key={metricCode}>
                    <td className="cell-title">{label}</td>
                    {rows.map((row) => {
                      const metric = row.metrics.find((m) => m.metric_code === metricCode);
                      return (
                        <td key={`${row.company.id}-${metricCode}`}>
                          {metric ? formatMetricValue(metric.metric_value, metric.unit) : "N/A"}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
