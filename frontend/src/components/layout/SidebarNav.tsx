export type NavKey = "dashboard" | "analysis" | "portfolio" | "chat" | "backtesting";

type Props = {
  activeView: NavKey;
  onChange: (value: NavKey) => void;
  ticker: string;
};

const NAV_ITEMS: Array<{ key: NavKey; label: string; hint: string }> = [
  { key: "dashboard", label: "DASHBOARD", hint: "coverage" },
  { key: "analysis", label: "COMPANY", hint: "valuation" },
  { key: "portfolio", label: "PORTFOLIO", hint: "multi-name" },
  { key: "chat", label: "CHAT", hint: "assistant" },
  { key: "backtesting", label: "BACKTEST", hint: "strategy" },
];

export default function SidebarNav({ activeView, onChange, ticker }: Props) {
  return (
    <div className="sidebar-nav">
      <div className="sidebar-brand terminal-grid-bg">
        <div className="sidebar-brand-title">FinChat</div>
        <div className="sidebar-brand-subtitle">RESEARCH TERMINAL</div>
      </div>

      <div className="sidebar-cover terminal-grid-bg">
        <div className="sidebar-cover-label">ACTIVE SYMBOL</div>
        <div className="sidebar-cover-ticker">{ticker || "-"}</div>
        <div className="sidebar-cover-meta">NASDAQ / EQUITY</div>
      </div>

      <nav className="sidebar-menu">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`sidebar-link ${activeView === item.key ? "active" : ""}`}
            onClick={() => onChange(item.key)}
          >
            <span className="sidebar-link-label">{item.label}</span>
            <span className="sidebar-link-hint">{item.hint}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer terminal-grid-bg">
        <div className="sidebar-footer-label">MODE</div>
        <div className="sidebar-footer-value">LIVE ANALYST WORKSPACE</div>
      </div>
    </div>
  );
}