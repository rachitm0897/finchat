import ValuationPanel from "../components/ValuationPanel";
import ScenarioPanel from "../components/ScenarioPanel";
import ReportExportPanel from "../components/ReportExportPanel";
import WorkspacePage from "../components/workspace/WorkspacePage";
import SectionGrid from "../components/workspace/SectionGrid";

type Props = { ticker: string };

export default function CompanyAnalysisPage({ ticker }: Props) {
  return (
    <WorkspacePage
      title="Intrinsic value and scenario framing"
      description="Discounted cash flow output, planning assumptions, scenario rows and export controls."
    >
      <SectionGrid columns="split">
        <ValuationPanel ticker={ticker} />
        <ScenarioPanel ticker={ticker} />
      </SectionGrid>
      <ReportExportPanel ticker={ticker} />
    </WorkspacePage>
  );
}