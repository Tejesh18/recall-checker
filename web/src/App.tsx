import { useEffect, useMemo, useState } from "react";
import { Matcher, type Index, type Verdict } from "./lib/matcher";
import { readOrders, type Purchase } from "./lib/orders";
import { readOrderFile } from "./lib/files";
import DropZone from "./components/DropZone";
import HowTo from "./components/HowTo";
import RecallCard from "./components/RecallCard";
import QuickCheck from "./components/QuickCheck";
import About from "./components/About";

export interface Result {
  purchase: Purchase;
  verdict: Verdict;
}

export default function App() {
  const [index, setIndex] = useState<Index | null>(null);
  const [loadError, setLoadError] = useState("");
  const [results, setResults] = useState<Result[] | null>(null);
  const [source, setSource] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}index.json`)
      .then((r) => r.json())
      .then(setIndex)
      .catch(() => setLoadError("Couldn't load the recall list. Try refreshing."));
  }, []);

  const matcher = useMemo(() => (index ? new Matcher(index) : null), [index]);

  function run(text: string, from: string) {
    if (!matcher) return;
    try {
      const purchases = readOrders(text);
      setResults(purchases.map((p) => ({ purchase: p, verdict: matcher.check(p.name, p.asin) })));
      setSource(from);
      setError("");
    } catch (e) {
      setError((e as Error).message);
      setResults(null);
    }
  }

  async function onFile(file: File) {
    try {
      run(await readOrderFile(file), file.name);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function onSample() {
    const text = await fetch(`${import.meta.env.BASE_URL}sample-orders.csv`).then((r) => r.text());
    run(text, "a sample order history");
  }

  const recalled = results?.filter((r) => r.verdict.kind === "recalled") ?? [];
  const maybe = results?.filter((r) => r.verdict.kind === "maybe") ?? [];

  return (
    <>
      <header>
        <h1>Recall Checker</h1>
        <p className="lede">
          Find out if anything you bought on Amazon was recalled. Drop in your order history and it gets checked
          against every U.S. consumer product recall since 2016.
        </p>
        <p className="private">
          Your orders stay on your computer. The matching runs in this page; nothing is uploaded anywhere.
        </p>
      </header>

      <main>
        {loadError && <p className="error">{loadError}</p>}

        {!results && (
          <>
            <DropZone ready={!!matcher} onFile={onFile} onSample={onSample} />
            {error && <p className="error">{error}</p>}
            <HowTo />
          </>
        )}

        {results && (
          <section className="results">
            <p className="summary">
              Checked {results.length} {results.length === 1 ? "item" : "items"} from {source}.{" "}
              {recalled.length === 0 && maybe.length === 0 && <strong>Nothing matched a recall.</strong>}
              {recalled.length > 0 && (
                <strong>
                  {recalled.length} {recalled.length === 1 ? "was" : "were"} recalled.
                </strong>
              )}{" "}
              <button className="link" onClick={() => setResults(null)}>
                Check another file
              </button>
            </p>

            {recalled.map((r, i) => (
              <RecallCard key={`r${i}`} result={r} />
            ))}

            {maybe.length > 0 && (
              <>
                <h2>Worth a second look</h2>
                <p className="note">
                  These look close to a recall, but not close enough to be sure. Compare the model number on the
                  product with the one in the recall.
                </p>
                {maybe.map((r, i) => (
                  <RecallCard key={`m${i}`} result={r} />
                ))}
              </>
            )}

            <details className="clear">
              <summary>Everything else ({results.length - recalled.length - maybe.length})</summary>
              <ul>
                {results
                  .filter((r) => r.verdict.kind === "clear")
                  .map((r, i) => (
                    <li key={i}>
                      {r.purchase.name} <span className="date">{r.purchase.date}</span>
                    </li>
                  ))}
              </ul>
            </details>
          </section>
        )}

        {matcher && <QuickCheck matcher={matcher} />}
        {index && <About index={index} />}
      </main>
    </>
  );
}
