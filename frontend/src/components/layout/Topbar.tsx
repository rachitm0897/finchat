type Props = {
  title: string;
  ticker: string;
  onGoToDashboard: () => void;
  onRefresh: () => void;
};

export default function Topbar({ title, ticker, onGoToDashboard, onRefresh }: Props) {
  return (
    <div className="topbar">
      <div className="topbar-title-group">
        <div className="topbar-title">{title}</div>
        <div className="topbar-subtitle">ACTIVE SYMBOL: {ticker || "-"}</div>
      </div>

      <div className="topbar-center">
        <div className="topbar-chip">
          <span className="topbar-chip-label">MODE</span>
          <strong>LIVE</strong>
        </div>
        <div className="topbar-chip">
          <span className="topbar-chip-label">ENV</span>
          <strong>ANALYST TERMINAL</strong>
        </div>
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