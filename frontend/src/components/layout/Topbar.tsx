
type Props = {
  title: string;
  ticker: string;
  onGoToDashboard: () => void;
  onRefresh: () => void;
};

const TAPE = [
  { label: "S&P", value: "6,368.00", change: "-1.67%", negative: true },
  { label: "NIFTY", value: "22,161.00", change: "-0.89%", negative: true },
  { label: "NIKKEI", value: "38,240.00", change: "+0.67%", negative: false },
  { label: "HSI", value: "19,842.00", change: "-1.12%", negative: true },
];

export default function Topbar({ title, ticker, onGoToDashboard, onRefresh }: Props) {
  return (
    <div className="topbar terminal-grid-bg">
      <div className="topbar-title-group">
        <div className="topbar-title">{title}</div>
        <div className="topbar-subtitle">ACTIVE INSTRUMENT: {ticker || "-"}</div>
      </div>

      <div className="market-tape">
        {TAPE.map((item) => (
          <div key={item.label} className="market-chip">
            <span className="market-chip-label">{item.label}</span>
            <strong>{item.value}</strong>
            <span className={item.negative ? "down" : "up"}>{item.change}</span>
          </div>
        ))}
      </div>

      <div className="topbar-actions">
        <button type="button" className="app-button app-button-ghost" onClick={onGoToDashboard}>
          DASHBOARD
        </button>
        <button type="button" className="app-button" onClick={onRefresh}>
          REFRESH
        </button>
      </div>
    </div>
  );
}
