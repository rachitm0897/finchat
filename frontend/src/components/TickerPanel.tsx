import { useState } from "react";
import { computeAnalytics, getJobStatus, ingestCompany, searchCompany, searchTickerUniverse } from "../api/api";
import type { CompanySummary, JobStatus } from "../types";
// import { searchTickerUniverse } from "../api/api";
type Props = {
  ticker: string;
  setTicker: (t: string) => void;
  onREFRESHRequested: () => void;
};

export default function TickerPanel({ ticker, setTicker, onREFRESHRequested }: Props) {
  const [query, setQuery] = useState(ticker);
  const [results, setResults] = useState<CompanySummary[]>([]);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ingestJob, setIngestJob] = useState<JobStatus | null>(null);
  const [computeJob, setComputeJob] = useState<JobStatus | null>(null);

  const pollJob = async (jobId: string, onDone?: () => void): Promise<JobStatus | null> => {
    let attempts = 0;
    while (attempts < 60) {
      attempts += 1;
      try {
        const res = await getJobStatus(jobId);
        const job = res.data.data as JobStatus;
        if (["success", "failed", "cancelled"].includes(job.status)) {
          if (job.status === "success" && onDone) onDone();
          return job;
        }
      } catch (err) {
        console.error("Job polling failed:", err);
        return null;
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    return null;
  };

  const handleLookup = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setLookupLoading(true);

    try {
      const res = await searchTickerUniverse(trimmed, 10);

      const rows = res.data?.data?.results || [];

      const options = rows.map((row: any) => ({
        id: row.symbol || row.ticker,
        ticker: row.symbol || row.ticker,
        name: row.description || row.name,
      }));

      setResults(options);
    } catch (err) {
      console.error("Ticker search failed:", err);
      setResults([]);
    }

    setLookupLoading(false);
  };

  const handleIngest = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    setIngestJob(null);
    try {
      const res = await ingestCompany(ticker, true);
      const payload = res.data.data;
      if (payload.mode === "async" && payload.job_id) {
        const finalJob = await pollJob(payload.job_id, onREFRESHRequested);
        if (finalJob) setIngestJob(finalJob);
      }
    } catch (err: any) {
      console.error("INGESTION failed:", err);
      alert(err.response?.data ? JSON.stringify(err.response.data, null, 2) : "INGESTION failed");
    }
    setLoading(false);
  };

  const handleCompute = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    setComputeJob(null);
    try {
      const res = await computeAnalytics(ticker, true);
      const payload = res.data.data;
      if (payload.mode === "async" && payload.job_id) {
        const finalJob = await pollJob(payload.job_id, onREFRESHRequested);
        if (finalJob) setComputeJob(finalJob);
      }
    } catch (err: any) {
      console.error("ANALYTICS failed:", err);
      alert(err.response?.data ? JSON.stringify(err.response.data, null, 2) : "ANALYTICS failed");
    }
    setLoading(false);
  };

  return (
    <section className="panel toolbar-panel">
      <div className="toolbar-grid">
        <div className="toolbar-main">
          <div className="toolbar-label">SECURITY LOOKUP</div>
          <div className="toolbar-input-row">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value.toUpperCase())}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleLookup();
              }}
              placeholder="Search ticker (AAPL, TSLA...)"
            />
            <button type="button" className="app-button" onClick={handleLookup} disabled={lookupLoading}>
              {lookupLoading ? "SEARCHing" : "SEARCH"}
            </button>
          </div>
          <div className="toolbar-results">
            {results.length === 0 ? (
              <div className="toolbar-results-empty">No search results loaded.</div>
            ) : (
              results.slice(0, 6).map((company) => (
                <button
                  type="button"
                  key={company.id}
                  className={`search-result ${ticker === company.ticker ? "active" : ""}`}
                  onClick={async () => {
                    setTicker(company.ticker);
                    setQuery(company.ticker);

                    await ingestCompany(company.ticker, true);
                    onREFRESHRequested();
                  }}
                >
                  <span className="search-result-symbol">{company.ticker}</span>
                  <span className="search-result-name">{company.name}</span>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="toolbar-side">
          <div className="toolbar-side-block">
            <div className="toolbar-label">SELECTED</div>
            <div className="ticker-readout">{ticker || "-"}</div>
            <div className="toolbar-actions">
              <button type="button" className="app-button" onClick={handleIngest} disabled={loading}>
                INGEST DATA
              </button>
              <button type="button" className="app-button app-button-secondary" onClick={handleCompute} disabled={loading}>
                COMPUTE METRICS
              </button>
            </div>
          </div>

          <div className="toolbar-side-block status-stack">
            <div className="status-line">
              <span>INGESTION</span>
              <strong>{ingestJob?.status || "idle"}</strong>
            </div>
            <div className="status-line">
              <span>ANALYTICS</span>
              <strong>{computeJob?.status || "idle"}</strong>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
