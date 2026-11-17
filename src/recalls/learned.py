"""Learn the match decision instead of hand-tuning a threshold.

The rule-based matcher finds candidate recalls and describes each one with a
few numbers (model number match, how much of the product name is covered,
whether the brand is also an everyday word...). A logistic regression
trained on the labeled pairs decides which of those are real.

Trained on title plus the catalog's model number, and scored both that way
and on the title alone, since an Amazon order export only has the product
name. (Training on both views was tried: title-only recall went down, from
.48 to .41 at the same precision, so it's trained on the full view.)

Evaluated per listing with 5-fold cross-validation (both views of a listing
stay in the same fold), then the final model is trained on everything and
checked against ordinary listings for false alarms.

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
VIEWS = ("title+model", "title")
CUTOFFS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def top_candidate(matcher: Matcher, title: str):
    cands = matcher.candidates(title)
    return cands[0] if cands else None


def featurize(m) -> list[float]:
    return [m.features[f] for f in FEATURES]


def text(item: dict, view: str) -> str:
    return f"{item['title']} {item['model']}" if view == "title+model" else item["title"]


def main() -> None:
    recalls = [r for r in json.load(open("data/recalls.json")) if r["source"] == "cpsc"]
    matcher = Matcher(recalls, word_df=json.load(open("data/word_df.json")))
    listings = list(load_labeled().values())
    recalled = np.array([bool(it["positives"]) for it in listings])

    # rows[i][view] = (features, is the top candidate right?) or None when there's no candidate
    rows = []
    for it in listings:
        r = {}
        for view in VIEWS:
            m = top_candidate(matcher, text(it, view))
            r[view] = (featurize(m), int(m.recall["id"] in it["positives"])) if m else None
        rows.append(r)

    def training_set(idx):
        pairs = [rows[i]["title+model"] for i in idx if rows[i]["title+model"]]
        return np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])

    probs = {v: np.full(len(listings), np.nan) for v in VIEWS}
    for train, test in StratifiedKFold(5, shuffle=True, random_state=7).split(np.zeros(len(listings)), recalled):
        clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(*training_set(train))
        for i in test:
            for v in VIEWS:
                if rows[i][v]:
                    probs[v][i] = clf.predict_proba([rows[i][v][0]])[0, 1]

    total = int(recalled.sum())
    print(f"{len(listings)} labeled listings, {total} recalled")
    table = {}
    for v in VIEWS:
        print(v)
        table[v] = []
        right = np.array([bool(rows[i][v] and rows[i][v][1]) for i in range(len(listings))])
        for cut in CUTOFFS:
            flagged = np.nan_to_num(probs[v], nan=0.0) >= cut
            tp, fp = int((flagged & right).sum()), int((flagged & ~right).sum())
            precision = tp / (tp + fp) if tp + fp else 0.0
            table[v].append({"cutoff": cut, "precision": precision, "recall": tp / total, "caught": tp, "false_alarms": fp})
            print(f"  cutoff {cut:.1f}: precision {precision:.2f}  recall {tp / total:.2f}  ({tp} caught, {fp} false alarms)")
    # the cutoff has to hold up in both cases: precision >= .9 in each, then the most caught
    ok = [i for i in range(len(CUTOFFS)) if all(table[v][i]["precision"] >= 0.9 for v in VIEWS)]
    ok = ok or [i for i in range(len(CUTOFFS)) if table["title+model"][i]["precision"] >= 0.9]
    best = max(ok or range(len(CUTOFFS)), key=lambda i: sum(table[v][i]["caught"] for v in VIEWS))
    cut = CUTOFFS[best]

    final = LogisticRegression(max_iter=2000, class_weight="balanced").fit(*training_set(range(len(listings))))
    ordinary = [json.loads(l) for l in open("data/amazon/sample.jsonl")]
    random.Random(7).shuffle(ordinary)
    alarms = {}
    for v in VIEWS:
        alarms[v] = 0
        for row in ordinary[:2000]:
            m = top_candidate(matcher, text({"title": row["title"], "model": row["details"].get("Item model number", "")}, v))
            if m and final.predict_proba([featurize(m)])[0, 1] >= cut:
                alarms[v] += 1
    print(f"chosen cutoff {cut}: ordinary listings flagged {alarms}")
    print("weights:", {f: round(float(w), 2) for f, w in zip(FEATURES, final.coef_[0])})

    Path("results").mkdir(exist_ok=True)
    Path("results/learned_eval.json").write_text(json.dumps({
        "cutoff": cut, "by_cutoff": table, "ordinary_false_alarms": alarms, "ordinary_checked": 2000,
        "weights": dict(zip(FEATURES, map(float, final.coef_[0]))), "intercept": float(final.intercept_[0]),
    }, indent=2))


if __name__ == "__main__":
    main()
