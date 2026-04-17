import { exportCompanyReportUrl } from "../api/api";

type Props = {
  ticker: string;
};

export default function ReportExportPanel({ ticker }: Props) {
  return (
    <section className="panel panel-tight terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>Export</h3>
          <div className="panel-subtitle">Direct report file downloads from the current API</div>
        </div>
      </div>
      <div className="toolbar-actions compact-actions">
        <a href={exportCompanyReportUrl(ticker, "json")} target="_blank" rel="noreferrer">
          <button type="button" className="app-button">Download JSON</button>
        </a>
        <a href={exportCompanyReportUrl(ticker, "markdown")} target="_blank" rel="noreferrer">
          <button type="button" className="app-button app-button-secondary">Download Markdown</button>
        </a>
      </div>
    </section>
  );
}
