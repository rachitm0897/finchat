import { useEffect, useMemo, useState } from "react";
import { getMetrics } from "../api/api";
import type { MetricRow } from "../types";
import { formatMetricValue, groupMetrics, GROUP_ORDER } from "../utils/metrics";

type Props = {
  ticker: string;
  refreshKey: number;
};

export default function MetricsPanel({ ticker, refreshKey }: Props) {
  const [metrics, setMetrics] = useState<MetricRow[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchMetrics = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    try {
      const res = await getMetrics(ticker, true, 100);
      setMetrics(res.data.data.results || []);
    } catch (err) {
      console.error(err);
      setMetrics([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    void fetchMetrics();
  }, [ticker, refreshKey]);

  const grouped = useMemo(() => groupMetrics(metrics), [metrics]);

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>Computed Metrics</h3>
          <div className="panel-subtitle">Latest annual snapshot grouped by financial lens</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={fetchMetrics} disabled={loading}>
          REFRESH
        </button>
      </div>

      {metrics.length === 0 ? (
        <div className="empty-state">No metrics loaded.</div>
      ) : (
        <div className="metric-section-stack">
          {GROUP_ORDER.filter((group) => grouped[group]?.length).map((group) => (
            <div key={group} className="metric-section">
              <div className="metric-section-title">{group}</div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Value</th>
                      <th>Code</th>
                      <th>Unit</th>
                      <th>As Of</th>
                    </tr>
                  </thead>
                  <tbody>
                    {grouped[group].map((metric) => (
                      <tr key={metric.id || metric.metric_code}>
                        <td>
                          <div className="cell-title">{metric.metric_name}</div>
                          {metric.notes ? <div className="cell-subtitle">{metric.notes}</div> : null}
                        </td>
                        <td className="cell-emphasis">{formatMetricValue(metric.metric_value, metric.unit)}</td>
                        <td>{metric.metric_code}</td>
                        <td>{metric.unit || "-"}</td>
                        <td>{metric.as_of_date || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
