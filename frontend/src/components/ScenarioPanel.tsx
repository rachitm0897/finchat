
import { useEffect, useState } from "react";
import { getScenarioAnalysis } from "../api/api";
import { formatAnyNumber } from "../utils/display";

type Props = {
  ticker: string;
};

export default function ScenarioPanel({ ticker }: Props) {
  const [scenario, setScenario] = useState<any>(null);

  const loadScenario = async () => {
    try {
      const res = await getScenarioAnalysis(ticker, 3);
      setScenario(res.data.data);
    } catch (err) {
      console.error("Scenario analysis failed:", err);
      setScenario(null);
    }
  };

  useEffect(() => {
    void loadScenario();
  }, [ticker]);

  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>SCENARIO ANALYSIS</h3>
          <div className="panel-subtitle">Bull, base and downside framing for the selected security</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={loadScenario}>REFRESH</button>
      </div>

      {!scenario ? (
        <div className="empty-state">No scenario analysis available.</div>
      ) : (
        <div className="subblock-grid three-up">
          {(scenario.scenarios || []).map((row: any) => (
            <div key={row.name} className="panel-subblock terminal-grid-bg">
              <div className="panel-subblock-title">{String(row.name).toUpperCase()}</div>
              <div className="scenario-price">{formatAnyNumber(row.implied_share_price)}</div>
              <div className="key-value-grid">
                <div className="mini-stat-row"><span>Revenue Growth</span><strong>{formatAnyNumber(row.revenue_growth)}</strong></div>
                <div className="mini-stat-row"><span>FCF Margin</span><strong>{formatAnyNumber(row.fcf_margin)}</strong></div>
                <div className="mini-stat-row"><span>Exit Multiple</span><strong>{formatAnyNumber(row.exit_multiple)}</strong></div>
                <div className="mini-stat-row"><span>Projected FCF</span><strong>{formatAnyNumber(row.projected_fcf)}</strong></div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
