
import { useEffect, useState } from "react";
import { getDCFValuation } from "../api/api";
import { formatAnyNumber } from "../utils/display";

type Props = {
  ticker: string;
};

export default function ValuationPanel({ ticker }: Props) {
  const [payload, setPayload] = useState<any>(null);

  const load = async () => {
    try {
      const res = await getDCFValuation(ticker);
      setPayload(res.data.data);
    } catch (err) {
      console.error("DCF valuation failed:", err);
      setPayload(null);
    }
  };

  useEffect(() => {
    void load();
  }, [ticker]);

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>DCF VALUATION</h3>
          <div className="panel-subtitle">Assumptions, terminal value logic and projection rows</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={load}>REFRESH</button>
      </div>

      {!payload ? (
        <div className="empty-state">No DCF valuation available.</div>
      ) : (
        <>
          <div className="subblock-grid two-up">
            <div className="panel-subblock terminal-grid-bg">
              <div className="panel-subblock-title">ASSUMPTIONS</div>
              <div className="key-value-grid">
                {Object.entries(payload.assumptions || {}).map(([key, value]) => (
                  <div key={key} className="mini-stat-row">
                    <span>{key}</span>
                    <strong>{formatAnyNumber(value)}</strong>
                  </div>
                ))}
              </div>
            </div>
            <div className="panel-subblock terminal-grid-bg">
              <div className="panel-subblock-title">VALUATION OUTPUT</div>
              <div className="key-value-grid">
                {Object.entries(payload.valuation || {}).map(([key, value]) => (
                  <div key={key} className="mini-stat-row">
                    <span>{key}</span>
                    <strong>{formatAnyNumber(value)}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Growth</th>
                  <th>Projected Revenue</th>
                  <th>Projected FCF</th>
                  <th>Discounted FCF</th>
                </tr>
              </thead>
              <tbody>
                {(payload.projection_rows || []).map((row: any) => (
                  <tr key={row.year}>
                    <td>{row.year}</td>
                    <td>{formatAnyNumber(row.growth_rate)}</td>
                    <td>{formatAnyNumber(row.projected_revenue)}</td>
                    <td>{formatAnyNumber(row.projected_fcf)}</td>
                    <td>{formatAnyNumber(row.discounted_fcf)}</td>
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
