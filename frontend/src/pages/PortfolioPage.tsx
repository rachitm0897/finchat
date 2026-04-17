import PortfolioActionsPanel from "../components/PortfolioActionsPanel";
import ComparisonPanel from "../components/ComparisonPanel";
import ComparisonVisualsPanel from "../components/ComparisonVisualsPanel";
import PeerRankingPanel from "../components/PeerRankingPanel";
import RankingVisualsPanel from "../components/RankingVisualsPanel";
import WorkspacePage from "../components/workspace/WorkspacePage";
import SectionGrid from "../components/workspace/SectionGrid";

type Props = { ticker: string };

export default function PortfolioPage({ ticker }: Props) {
  return (
    <WorkspacePage
      title="Portfolio research"
      description="Portfolio actions, ranking, comparison, and multi-name relative analysis."
    >
      <ComparisonPanel ticker={ticker} />
      <SectionGrid columns="split">
        <ComparisonVisualsPanel />
        <PeerRankingPanel />
      </SectionGrid>
      <SectionGrid columns="split">
        <RankingVisualsPanel />
        <PortfolioActionsPanel />
      </SectionGrid>
    </WorkspacePage>
  );
}