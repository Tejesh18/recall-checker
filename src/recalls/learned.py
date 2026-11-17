"""Learn the match decision instead of hand-tuning a threshold.

The rule-based matcher finds candidate recalls and describes each one with a
few numbers (model number match, how much of the product name is covered,
whether the brand is also an everyday word...). A logistic regression
trained on the labeled pairs decides which of those are real.

Evaluated per listing with 5-fold cross-validation, then the final model is
trained on everything and checked against ordinary listings for false alarms.

    python -m recalls.learned
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from .evaluate import load_labeled
from .match import Matcher

FEATURES = ["model", "coverage", "shared", "rare_shared", "common_brand", "brand_words",
            "brand_at_start", "title_words", "products_in_recall"]


def top_candidate(matcher: Matcher, title: str):
    cands = matcher.candidates(title)
    return cands[0] if cands else None


def featurize(m) -> list[float]:
    return [m.features[f] for f in FEATURES]


def main() -> None:
    recalls = [r for r in json.load(open("data/recalls.json")) if r["source"] == "cpsc"]
    matcher = Matcher(recalls, word_df=json.load(open("data/word_df.json")))
    labeled = load_labeled()

    rows, uncatchable = [], 0
    for item in labeled.values():
        m = top_candidate(matcher, f"{item['title']} {item['model']}")
        if m is None:
            uncatchable += bool(item["positives"])
            continue
        rows.append((featurize(m), int(m.recall["id"] in item["positives"]), bool(item["positives"])))
    X = np.array([r[0] for r in rows])
    y = np.array([r[1] for r in rows])
    recalled = np.array([r[2] for r in rows])
    total_recalled = int(recalled.sum()) + uncatchable

    probs = np.zeros(len(y))
    for train, test in StratifiedKFold(5, shuffle=True, random_state=7).split(X, y):
        clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(X[train], y[train])
        probs[test] = clf.predict_proba(X[test])[:, 1]

    print(f"{len(labeled)} labeled listings, {total_recalled} recalled ({uncatchable} with no candidate at all)")
    table = []
    for cut in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        flagged = probs >= cut
        tp = int((flagged & (y == 1)).sum())
        fp = int((flagged & (y == 0)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / total_recalled
        table.append((cut, precision, recall, tp, fp))
        print(f"  cutoff {cut:.1f}: precision {precision:.2f}  recall {recall:.2f}  ({tp} caught, {fp} false alarms)")
    good = [t for t in table if t[1] >= 0.9] or table
    cut = max(good, key=lambda t: t[2])[0]

    final = LogisticRegression(max_iter=2000, class_weight="balanced").fit(X, y)
    rng = random.Random(7)
    ordinary = [json.loads(l) for l in open("data/amazon/sample.jsonl")]
    rng.shuffle(ordinary)
    alarms = 0
    for row in ordinary[:2000]:
        m = top_candidate(matcher, f"{row['title']} {row['details'].get('Item model number', '')}")
        if m and final.predict_proba([featurize(m)])[0, 1] >= cut:
            alarms += 1
    print(f"chosen cutoff {cut}: {alarms}/2000 ordinary listings flagged")
    print("weights:", {f: round(float(w), 2) for f, w in zip(FEATURES, final.coef_[0])})

    Path("results").mkdir(exist_ok=True)
    Path("results/learned_eval.json").write_text(json.dumps({
        "cutoff": cut, "by_cutoff": [dict(zip(["cutoff", "precision", "recall", "caught", "false_alarms"], t)) for t in table],
        "ordinary_false_alarms": alarms, "ordinary_checked": 2000,
        "weights": dict(zip(FEATURES, map(float, final.coef_[0]))), "intercept": float(final.intercept_[0]),
    }, indent=2))


if __name__ == "__main__":
    main()
