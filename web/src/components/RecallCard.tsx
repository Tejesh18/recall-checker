import type { Result } from "../App";

const fmt = (d: string) =>
  d ? new Date(d + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "";

export default function RecallCard({ result }: { result: Result }) {
  const { purchase, verdict } = result;
  if (verdict.kind === "clear") return null;
  const { recall, why, prob } = verdict.match;
  const boughtAfter = purchase.date && purchase.date > recall.date;

  return (
    <article className={`card ${verdict.kind}`}>
      {recall.image && (
        <img src={recall.image} alt="" loading="lazy" onError={(e) => (e.currentTarget.style.visibility = "hidden")} />
      )}
      <div>
        <p className="bought">
          You bought <b>{purchase.name}</b>
          {purchase.date && <> on {fmt(purchase.date)}</>}
        </p>
        <h3>
          <a href={recall.url} target="_blank" rel="noreferrer">
            {recall.title}
          </a>
        </h3>
        <p className="meta">
          Recalled {fmt(recall.date)}
          {recall.units && <> &middot; Units: {recall.units}</>}
        </p>
        {recall.hazard && (
          <p>
            <b>Hazard:</b> {recall.hazard}
          </p>
        )}
        {recall.remedy && (
          <p>
            <b>What to do:</b> {recall.remedy}
          </p>
        )}
        {boughtAfter && (
          <p className="note">
            You bought this after the recall was announced. It may be a fixed unit, so check the model and date codes
            listed in the recall.
          </p>
        )}
        <p className="why">
          Matched on {why.join("; ")} ({Math.round(prob * 100)}% sure)
        </p>
      </div>
    </article>
  );
}
