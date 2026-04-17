type Props = {
  ticker: string;
};

export default function BacktestingPlaceholder({ ticker }: Props) {
  return (
    <div className="panel panel-tight">
      <div className="panel-header">
        <div>
          <h3>Backtesting integration placeholder</h3>
          <div className="panel-subtitle">Prepared for {ticker || "selected symbol"}</div>
        </div>
      </div>

      <div className="placeholder-grid">
        <div className="placeholder-block">
          <div className="placeholder-title">Strategy Parameters</div>
          <ul className="placeholder-list">
            <li>Strategy selector</li>
            <li>Date range</li>
            <li>Benchmark / rebalance controls</li>
            <li>Position sizing and costs</li>
          </ul>
        </div>

        <div className="placeholder-block">
          <div className="placeholder-title">Result Containers</div>
          <ul className="placeholder-list">
            <li>Equity curve</li>
            <li>Drawdown and return table</li>
            <li>Trade log and scenario stats</li>
            <li>Saved run history</li>
          </ul>
        </div>
      </div>

      <div className="empty-state compact">
        The current backend snapshot exposes ingestion, analytics, comparison, chat and report endpoints, but no backtesting routes.
        The screen structure is ready so the API can be dropped in without redesigning the rest of the app again. Because repeating bad work is apparently a cherished tradition.
      </div>
    </div>
  );
}
