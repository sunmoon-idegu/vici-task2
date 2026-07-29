import { useMemo, useState } from "react";

import { extractFiling } from "./api.js";

const EXAMPLE_URLS = [
  {
    label: "Coca-Cola-1994",
    url:
      "https://www.sec.gov/Archives/edgar/data/21344/" +
      "0000021344-95-000007.txt",
  },
  {
    label: "Network-1-2006",
    url:
      "https://www.sec.gov/Archives/edgar/data/1065078/" +
      "000107261307000908/form10-ksb_14962.txt",
  },
  {
    label: "Apple-2024",
    url:
      "https://www.sec.gov/Archives/edgar/data/320193/" +
      "000032019324000123/aapl-20240928.htm",
  },
  {
    label: "Microsoft-2024",
    url:
      "https://www.sec.gov/Archives/edgar/data/789019/" +
      "000095017024087843/msft-20240630.htm",
  },
  {
    label: "Coca-Cola-2025",
    url:
      "https://www.sec.gov/Archives/edgar/data/21344/" +
      "000162828026010047/ko-20251231.htm",
  },
];

function formatScore(score) {
  return typeof score === "number" ? score.toFixed(3) : "—";
}

function scoreTone(score) {
  if (score >= 0.9) return "high";
  if (score >= 0.75) return "medium";
  return "low";
}

function ItemViewer({ item }) {
  if (!item) {
    return null;
  }

  return (
    <article className="item-viewer">
      <div className="item-title-row">
        <div>
          <p className="eyebrow">Extracted section</p>
          <h2>
            Item {item.item}
            {item.title ? <span> · {item.title}</span> : null}
          </h2>
        </div>
        <span className={`score-pill ${scoreTone(item.confidence.score)}`}>
          {formatScore(item.confidence.score)}
        </span>
      </div>

      {item.content_html ? (
        <div
          className="filing-content"
          dangerouslySetInnerHTML={{ __html: item.content_html }}
        />
      ) : (
        <pre className="filing-content plain">{item.content}</pre>
      )}
    </article>
  );
}

export default function App() {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedItem = result?.items?.[selectedIndex] || null;
  const itemCount = result?.items?.length || 0;

  const confidenceTone = useMemo(
    () => scoreTone(result?.confidence),
    [result?.confidence],
  );

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setError("Enter an SEC filing URL.");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const extraction = await extractFiling(trimmedUrl);
      setResult(extraction);
      setSelectedIndex(0);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  function useExample(exampleUrl) {
    setUrl(exampleUrl);
    setError("");
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero-inner">
          <div className="hero-copy">
            <p className="hero-eyebrow">SEC filing analysis</p>
            <h1>10-K Item Extractor</h1>
            <p>
              Extract every Item from an SEC 10-K filing and review the
              confidence of each result.
            </p>
          </div>

          <form className="url-form" onSubmit={handleSubmit}>
            <label htmlFor="filing-url" className="sr-only">
              SEC filing URL
            </label>
            <div className="url-input-row">
              <input
                id="filing-url"
                type="url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="Paste an SEC Archives URL"
                autoComplete="url"
                disabled={isLoading}
              />
              <button type="submit" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <span className="spinner" aria-hidden="true" />
                    Extracting…
                  </>
                ) : (
                  "Extract"
                )}
              </button>
            </div>

            <div className="examples">
              <span>Examples</span>
              {EXAMPLE_URLS.map((example) => (
                <button
                  key={example.label}
                  type="button"
                  onClick={() => useExample(example.url)}
                  disabled={isLoading}
                >
                  {example.label}
                </button>
              ))}
            </div>
          </form>

          {error ? (
            <div className="error-banner">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <circle
                  cx="12"
                  cy="12"
                  r="9"
                  stroke="currentColor"
                  strokeWidth="2"
                />
                <path
                  d="M12 8v5"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <circle cx="12" cy="16" r="1" fill="currentColor" />
              </svg>
              <span>{error}</span>
            </div>
          ) : null}
        </div>
      </header>

      {isLoading ? (
        <main className="loading-state">
          <span className="spinner" style={{ width: 28, height: 28 }} />
          <h2>Reading the filing</h2>
          <p>Downloading, extracting Items, and calculating confidence.</p>
        </main>
      ) : null}

      {!isLoading && !result ? (
        <main className="empty-state">
          <div className="state-icon">
            <svg
              width="26"
              height="26"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
              <path
                d="M14 3v5h5"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
              <path
                d="M9 13h6M9 16.5h6M9 9.5h2.5"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <h2>No filing extracted yet</h2>
          <p>Enter an official SEC Archives HTML or TXT filing URL above.</p>
        </main>
      ) : null}

      {!isLoading && result ? (
        <main className="results-layout">
          <aside className="results-sidebar">
            <section className="filing-summary">
              <p className="eyebrow">Extraction confidence</p>
              <div className="summary-score-row">
                <strong className={confidenceTone}>
                  {formatScore(result.confidence)}
                </strong>
              </div>
              <p>{itemCount} Items extracted</p>
            </section>

            <nav className="item-navigation" aria-label="Extracted Items">
              {result.items.map((item, index) => (
                <button
                  key={`${item.item}-${item.start}`}
                  type="button"
                  className={index === selectedIndex ? "active" : ""}
                  onClick={() => setSelectedIndex(index)}
                >
                  <span>Item {item.item}</span>
                  <small>{formatScore(item.confidence.score)}</small>
                </button>
              ))}
            </nav>
          </aside>

          <ItemViewer item={selectedItem} />
        </main>
      ) : null}
    </div>
  );
}
