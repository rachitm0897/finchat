import { useEffect, useMemo, useRef, useState } from "react";

export type SearchableOption = {
  id: string;
  ticker: string;
  name: string;
};

type Props = {
  options: SearchableOption[];
  value: string;
  onChange: (ticker: string) => void;
  placeholder?: string;
  loading?: boolean;
};

export function SearchableTickerSelect({
  options,
  value,
  onChange,
  placeholder = "Search ticker or company",
  loading = false,
}: Props) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return options.slice(0, 12);
    return options
      .filter(
        (option) =>
          option.ticker.toLowerCase().includes(normalized) ||
          option.name.toLowerCase().includes(normalized)
      )
      .slice(0, 12);
  }, [options, query]);

  return (
    <div className="search-select" ref={wrapperRef}>
      <div className="search-select-input-wrap">
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value.toUpperCase());
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="app-input"
        />
        <span className="search-select-hint">{loading ? "Loading" : `${options.length} loaded`}</span>
      </div>

      {open ? (
        <div className="search-select-menu">
          {filtered.length === 0 ? (
            <div className="search-select-empty">No matching companies</div>
          ) : (
            filtered.map((option) => (
              <button
                type="button"
                key={option.id}
                className={`search-select-option ${value === option.ticker ? "active" : ""}`}
                onClick={() => {
                  onChange(option.ticker);
                  setQuery(option.ticker);
                  setOpen(false);
                }}
              >
                <div className="search-select-ticker">{option.ticker}</div>
                <div className="search-select-name">{option.name}</div>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
