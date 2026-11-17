"""How good is the matcher?

Scored per listing, the way a user experiences it:
  - a listing labeled recalled counts as caught only if the matcher returns
    the *right* recall
  - any recall returned for a listing that isn't recalled is a false alarm

Two sets:
  labeled   the hand-labeled candidate pairs (labels/pairs.csv): hard cases,
            same brand and similar words
  ordinary  random listings that never came near a recall: how often does
            the matcher cry wolf on everyday products?

    python -m recalls.evaluate
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from .match import Matcher


def load_labeled() -> dict[str, dict]:
    listings: dict[str, dict] = {}
    for r in csv.DictReader(open("labels/pairs.csv")):
        item = listings.setdefault(r["asin"], {"title": r["listing_title"], "model": r["listing_model"], "positives": set()})
        if r["label"] == "1":
            item["positives"].add(r["recall_id"])
    return listings


def evaluate(matcher: Matcher, ordinary_n: int = 2000, seed: int = 7) -> dict:
    labeled = load_labeled()
    tp = fp = fn = tn = wrong = 0
    misses, alarms = [], []
    for asin, item in labeled.items():
        text = f"{item['title']} {item['model']}"
        m = matcher.match(text)
        got = m.recall["id"] if m else None
        if item["positives"]:
            if got in item["positives"]:
                tp += 1
            else:
                fn += 1
                if got:
                    wrong += 1
                misses.append((item["title"], sorted(item["positives"]), got))
        else:
            if got:
                fp += 1
                alarms.append((item["title"], got, m.reasons if m else []))
            else:
                tn += 1

    rows = [json.loads(l) for l in open("data/amazon/sample.jsonl")]
    random.Random(seed).shuffle(rows)
    ordinary = rows[:ordinary_n]
    ordinary_alarms = []
    for row in ordinary:
        model = row["details"].get("Item model number", "")
        m = matcher.match(f"{row['title']} {model}")
        if m:
            ordinary_alarms.append((row["title"], m.recall["id"], m.reasons))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "labeled_listings": len(labeled),
        "recalled": tp + fn,
        "caught": tp,
        "missed": fn,
        "matched_wrong_recall": wrong,
        "false_alarms": fp,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "ordinary_checked": len(ordinary),
        "ordinary_false_alarms": len(ordinary_alarms),
        "_misses": misses,
        "_alarms": alarms,
        "_ordinary_alarms": ordinary_alarms,
    }


def main() -> None:
    recalls = [r for r in json.load(open("data/recalls.json")) if r["source"] == "cpsc"]
    df = json.load(open("data/word_df.json"))
    results = {}
    for threshold in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
        res = evaluate(Matcher(recalls, word_df=df, threshold=threshold))
        results[threshold] = res
        print(f"threshold {threshold}: precision {res['precision']:.2f}  recall {res['recall']:.2f}  "
              f"caught {res['caught']}/{res['recalled']}  false alarms {res['false_alarms']} labeled, "
              f"{res['ordinary_false_alarms']}/{res['ordinary_checked']} ordinary")
    best = max(results, key=lambda t: (results[t]["precision"] >= 0.9, results[t]["recall"]))
    res = results[best]
    print(f"\nchosen threshold {best}")
    print("misses:")
    for title, want, got in res["_misses"][:10]:
        print(f"  - {title[:80]} | want {want[0]} got {got}")
    print("false alarms (labeled):")
    for title, got, reasons in res["_alarms"][:8]:
        print(f"  - {title[:80]} -> {got} {reasons}")
    print("false alarms (ordinary):")
    for title, got, reasons in res["_ordinary_alarms"][:8]:
        print(f"  - {title[:80]} -> {got} {reasons}")
    out = {str(t): {k: v for k, v in r.items() if not k.startswith("_")} for t, r in results.items()}
    Path("results").mkdir(exist_ok=True)
    Path("results/match_eval.json").write_text(json.dumps({"chosen": best, "by_threshold": out}, indent=2))


if __name__ == "__main__":
    main()
