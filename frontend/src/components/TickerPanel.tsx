import { useEffect, useMemo, useState } from "react";
import {
  computeAnalytics,
  getJobStatus,
  ingestCompany,
  listAvailableCompanies,
  searchTickerUniverse,
} from "../api/api";
import type { CompanySummary, JobStatus, TickerUniverseResult } from "../types";

type Props = {
  ticker: string;
  setTicker: (t: string) => void;
  onRefreshRequested: () => void;
};

const FINAL_JOB_STATES = ["success", "failed", "cancelled"] as const;

function formatJobLabel(job: JobStatus | null) {
  if (!job) return "idle";
  return job.status;
}

export default function TickerPanel({ ticker, setTicker, onRefreshRequested }: Props) {
  const [query, setQuery] = useState(ticker);
  const [results, setResults] = useState<TickerUniverseResult[]>([]);
  const [availableCompanies, setAvailableCompanies] = useState<CompanySummary[]>([]);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ingestJob, setIngestJob] = useState<JobStatus | null>(null);
  const [computeJob, setComputeJob] = useState<JobStatus | null>(null);

  useEffect(() => {
    setQuery(ticker);
  }, [ticker]);

  const loadAvailableCompanies = async () => {
    try {
      const res = await listAvailableCompanies(250);
      setAvailableCompanies(res.data?.data?.results || []);
    } catch (err) {
      console.error("Failed to load available companies:", err);
      setAvailableCompanies([]);
    }
  };

  useEffect(() => {
    void loadAvailableCompanies();
  }, []);

  const pollJob = async (jobId: string, onDone?: () => Promise<void> | void): Promise<JobStatus | null> => {
    let attempts = 0;

    while (attempts < 90) {
      attempts += 1;
      try {
        const res = await getJobStatus(jobId);
        const job = res.data.data as JobStatus;

        if (FINAL_JOB_STATES.includes(job.status as (typeof FINAL_JOB_STATES)[number])) {
          if (job.status === "success" && onDone) {
            await onDone();
          }
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
    if (!trimmed) {
      setResults([]);
      return;
    }

    setLookupLoading(true);

    try {
      const res = await searchTickerUniverse(trimmed, 10);
      const rows = res.data?.data?.results || [];
      setResults(rows);
    } catch (err) {
      console.error("Ticker search failed:", err);
      setResults([]);
    } finally {
      setLookupLoading(false);
    }
  };

  const runIngest = async (nextTicker: string) => {
    const selectedTicker = nextTicker.trim().toUpperCase();
    if (!selectedTicker) return;

    setLoading(true);
    setIngestJob(null);

    try {
      const res = await ingestCompany(selectedTicker, true);
      const payload = res.data?.data;

      if (payload?.mode === "async" && payload?.job_id) {
        const finalJob = await pollJob(payload.job_id, async () => {
          await loadAvailableCompanies();
          onRefreshRequested();
        });
        if (finalJob) setIngestJob(finalJob);
      }
    } catch (err: any) {
      console.error("INGESTION failed:", err);
      alert(err.response?.data ? JSON.stringify(err.response.data, null, 2) : "INGESTION failed");
    } finally {
      setLoading(false);
    }
  };

  const runCompute = async () => {
    if (!ticker.trim()) return;

    setLoading(true);
    setComputeJob(null);

    try {
      const res = await computeAnalytics(ticker, true);
      const payload = res.data?.data;

      if (payload?.mode === "async" && payload?.job_id) {
        const finalJob = await pollJob(payload.job_id, onRefreshRequested);
        if (finalJob) setComputeJob(finalJob);
      }
    } catch (err: any) {
      console.error("ANALYTICS failed:", err);
      alert(err.response?.data ? JSON.stringify(err.response.data, null, 2) : "ANALYTICS failed");
    } finally {
      setLoading(false);
    }
  };

  const activeResultCount = useMemo(() => results.slice(0, 6).length, [results]);

  return (
    <section className="panel panel-tight toolbar-panel">
      <div className="panel-header panel-header-tight">
        <div>
          <h3>SECURITY CONTROL</h3>
          <div className="panel-subtitle">
            Search universe, switch active ticker, ingest data, compute analytics
          </div>
        </div>
        <div className="toolbar-status-row">
          <span className={`status-pill ${formatJobLabel(ingestJob)}`}>INGEST {formatJobLabel(ingestJob)}</span>
          <span className={`status-pill ${formatJobLabel(computeJob)}`}>ANALYTICS {formatJobLabel(computeJob)}</span>
        </div>
      </div>

      <div className="toolbar-grid toolbar-grid-bloomberg">
        <div className="toolbar-main">
          <div className="toolbar-block">
            <div className="toolbar-label">LOOKUP UNIVERSE</div>
            <div className="toolbar-input-row">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value.toUpperCase())}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleLookup();
                }}
                placeholder="Search ticker or company"
              />
              <button type="button" className="app-button" onClick={handleLookup} disabled={lookupLoading}>
                {lookupLoading ? "SEARCHING" : "SEARCH"}
              </button>
            </div>

            <div className="toolbar-results toolbar-results-list">
              {activeResultCount === 0 ? (
                <div className="empty-state compact">No search results loaded.</div>
              ) : (
                results.slice(0, 6).map((company, idx) => {
                  const resolvedTicker = (company.symbol || company.ticker || "").toUpperCase();
                  const resolvedName = company.description || company.name || "Unknown company";

                  return (
                    <button
                      type="button"
                      key={`${resolvedTicker}-${idx}`}
                      className={`search-result ${ticker === resolvedTicker ? "active" : ""}`}
                      onClick={() => {
                        setTicker(resolvedTicker);
                        setQuery(resolvedTicker);
                      }}
                    >
                      <span className="search-result-symbol">{resolvedTicker}</span>
                      <span className="search-result-name">{resolvedName}</span>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>

        <div className="toolbar-side">
          <div className="toolbar-side-block">
            <div className="toolbar-label">ACTIVE TICKER</div>
            <div className="ticker-readout">{ticker || "-"}</div>
          </div>

          <div className="toolbar-side-block">
            <div className="toolbar-label">INGESTED UNIVERSE</div>
            <select
              value={ticker}
              onChange={(e) => {
                const nextTicker = e.target.value.toUpperCase();
                setTicker(nextTicker);
                setQuery(nextTicker);
              }}
            >
              <option value="">SELECT AVAILABLE TICKER</option>
              {availableCompanies.map((company) => (
                <option key={company.id} value={company.ticker}>
                  {company.ticker} - {company.name}
                </option>
              ))}
            </select>
          </div>

          <div className="toolbar-side-block">
            <div className="toolbar-actions toolbar-actions-stacked">
              <button
                type="button"
                className="app-button"
                onClick={() => void runIngest(ticker)}
                disabled={loading}
              >
                INGEST DATA
              </button>
              <button
                type="button"
                className="app-button app-button-secondary"
                onClick={() => void runCompute()}
                disabled={loading}
              >
                COMPUTE METRICS
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}