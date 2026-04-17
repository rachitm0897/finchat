import AnalysisSummaryPanel from "../components/AnalysisSummaryPanel";
import TrendChartsPanel from "../components/TrendChartsPanel";
import MetricsPanel from "../components/MetricsPanel";
import WorkspacePage from "../components/workspace/WorkspacePage";
import SectionGrid from "../components/workspace/SectionGrid";

type Props = {
  ticker: string;
  refreshKey: number;
};

export default function DashboardPage({ ticker, refreshKey }: Props) {
  return (
    <WorkspacePage
      title="Coverage overview"
      description="Live symbol context, summary flags, operating trend panels and latest computed metrics."
    >
      <SectionGrid columns="split">
        <AnalysisSummaryPanel ticker={ticker} refreshKey={refreshKey} />
        <TrendChartsPanel ticker={ticker} refreshKey={refreshKey} />
      </SectionGrid>
      <MetricsPanel ticker={ticker} refreshKey={refreshKey} />
    </WorkspacePage>
  );
}