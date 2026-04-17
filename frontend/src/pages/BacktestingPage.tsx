import BacktestingPanel from "../components/BackTestingPanel";
import WorkspacePage from "../components/workspace/WorkspacePage";

type Props = { ticker: string };

export default function BacktestingPage({ ticker }: Props) {
  return (
    <WorkspacePage
      title="Backtesting workbench"
      description="Run deterministic historical strategy tests, review drawdown and equity curves, and inspect saved runs."
    >
      <BacktestingPanel ticker={ticker} />
    </WorkspacePage>
  );
}