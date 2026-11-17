import { useState } from "react";
import type { Matcher } from "../lib/matcher";

// For checking one thing without exporting anything: type what's on the box.
export default function QuickCheck({ matcher }: { matcher: Matcher }) {
  const [q, setQ] = useState("");
  const v = q.trim().length > 3 ? matcher.check(q) : null;

  return (
    <section className="quick">
      <h2>Or check one thing</h2>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Brand, product and model number, e.g. Secura air fryer SAF-53D"
      />
      {v && v.kind === "clear" && <p className="small">No recall matches that.</p>}
      {v && v.kind !== "clear" && (
        <p>
          {v.kind === "recalled" ? "Recalled: " : "Possibly: "}
          <a href={v.match.recall.url} target="_blank" rel="noreferrer">
            {v.match.recall.title}
          </a>{" "}
          <span className="small">({v.match.recall.date})</span>
        </p>
      )}
    </section>
  );
}
