import { useMemo, useState } from "react";
import TickerPanel from "./components/TickerPanel";
import ChatPanel from "./components/ChatPanel";
import AppShell from "./components/layout/AppShell";
import SidebarNav, { type NavKey } from "./components/layout/SidebarNav";
import Topbar from "./components/layout/Topbar";
import DashboardPage from "./pages/DashboardPage";
import CompanyAnalysisPage from "./pages/CompanyAnalysisPage";
import BacktestingPage from "./pages/BacktestingPage";
import PortfolioPage from "./pages/PortfolioPage";
import WorkspacePage from "./components/workspace/WorkspacePage";
import "./styles.css";

function App() {
  const [ticker, setTicker] = useState("AAPL");
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeView, setActiveView] = useState<NavKey>("dashboard");

  const appTitle = useMemo(() => {
    switch (activeView) {
      case "dashboard":
        return "MARKET MONITOR";
      case "analysis":
        return "COMPANY ANALYSIS";
      case "portfolio":
        return "PORTFOLIO WORKBENCH";
      case "chat":
        return "RESEARCH TERMINAL";
      case "backtesting":
        return "STRATEGY LAB";
      default:
        return "WORKSPACE";
    }
  }, [activeView]);

  const handleRefreshRequested = () => setRefreshKey((prev) => prev + 1);

  return (
    <AppShell
      sidebar={<SidebarNav activeView={activeView} onChange={setActiveView} ticker={ticker} />}
      topbar={
        <Topbar
          title={appTitle}
          ticker={ticker}
          onGoToDashboard={() => setActiveView("dashboard")}
          onRefresh={handleRefreshRequested}
        />
      }
    >
      <TickerPanel
        ticker={ticker}
        setTicker={setTicker}
        onRefreshRequested={handleRefreshRequested}
      />

      {activeView === "dashboard" && <DashboardPage ticker={ticker} refreshKey={refreshKey} />}
      {activeView === "analysis" && <CompanyAnalysisPage ticker={ticker} />}
      {activeView === "portfolio" && <PortfolioPage ticker={ticker} />}
      {activeView === "backtesting" && <BacktestingPage ticker={ticker} />}
      {activeView === "chat" && (
        <WorkspacePage
          title="Research assistant"
          description="Tool-backed analyst chat with session history and company context."
        >
          <ChatPanel ticker={ticker} />
        </WorkspacePage>
      )}
    </AppShell>
  );
}

export default App;