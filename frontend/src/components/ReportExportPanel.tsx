import { exportCompanyReportUrl } from "../api/api";

type Props = {
  ticker: string;
};

export default function ReportExportPanel({ ticker }: Props) {
  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>EXPORT</h3>
          <div className="panel-subtitle">Direct report downloads for the active ticker</div>
        </div>
      </div>

      <div className="toolbar-actions compact-actions">
        <a className="app-button" href={exportCompanyReportUrl(ticker, "json")} target="_blank" rel="noreferrer">
          DOWNLOAD JSON
        </a>
        <a
          className="app-button app-button-secondary"
          href={exportCompanyReportUrl(ticker, "markdown")}
          target="_blank"
          rel="noreferrer"
        >
          DOWNLOAD MARKDOWN
        </a>
      </div>
    </section>
  );
}