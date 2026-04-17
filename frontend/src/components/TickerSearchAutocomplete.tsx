import { useEffect, useRef, useState } from "react";
import { searchTickerUniverse } from "../api/api";
import type { TickerUniverseResult } from "../types";

type Props = {
  value: string;
  onChange: (ticker: string) => void;
  onSelect?: (item: TickerUniverseResult) => void;
};

export default function TickerSearchAutocomplete({ value, onChange, onSelect }: Props) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<TickerUniverseResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(0);

  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed || trimmed.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }

    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const res = await searchTickerUniverse(trimmed, 12);
        const rows = res.data?.data?.results || [];
        setResults(rows);
        setOpen(true);
        setHighlightIndex(0);
      } catch (err) {
        console.error("Ticker universe search failed:", err);
        setResults([]);
        setOpen(false);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  const handleSelect = (item: TickerUniverseResult) => {
    setQuery(item.ticker);
    onChange(item.ticker);
    if (onSelect) onSelect(item);
    setOpen(false);
  };

  return (
    <div className="ticker-search" ref={wrapperRef}>
      <label htmlFor="ticker-universe-search" className="field-label">
        Search Stock Universe
      </label>

      <div className="ticker-search-input-wrap">
        <input
          id="ticker-universe-search"
          value={query}
          onChange={(e) => {
            const next = e.target.value.toUpperCase();
            setQuery(next);
            onChange(next);
          }}
          onFocus={() => {
            if (results.length > 0) setOpen(true);
          }}
          onKeyDown={(e) => {
            if (!open || results.length === 0) return;

            if (e.key === "ArrowDown") {
              e.preventDefault();
              setHighlightIndex((prev) => Math.min(prev + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setHighlightIndex((prev) => Math.max(prev - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              handleSelect(results[highlightIndex]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder="Search ticker or company name"
          autoComplete="off"
        />
        {loading && <div className="ticker-search-loading">Searching...</div>}
      </div>

      {open && (
        <div className="ticker-search-dropdown">
          {results.length === 0 ? (
            <div className="ticker-search-empty">No matching tickers found.</div>
          ) : (
            results.map((item, index) => (
              <button
                key={`${item.ticker}-${item.exchange}-${index}`}
                type="button"
                className={`ticker-search-option ${index === highlightIndex ? "active" : ""}`}
                onClick={() => handleSelect(item)}
              >
                <div className="ticker-search-main">
                  <span className="ticker-search-symbol">{item.ticker}</span>
                  <span className="ticker-search-name">{item.name}</span>
                </div>
                <div className="ticker-search-meta">
                  <span>{item.exchange || "Unknown exchange"}</span>
                  <span>{item.is_ingested ? "Ingested" : "Not ingested"}</span>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}