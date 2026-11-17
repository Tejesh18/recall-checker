"""Export what the website needs to match in the browser.

web/public/index.json   recalls, already broken into the pieces the matcher
                        uses (brands, product word sets, model numbers), plus
                        word frequencies and the learned weights
web/src/lib/__fixtures__/parity.json
                        titles and what the Python matcher decides for them,
                        so the TypeScript port can be tested against it

    python -m recalls.export
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .evaluate import load_labeled
from .learned import FEATURES
from .match import Matcher


def main() -> None:
    recalls = [r for r in json.load(open("data/recalls.json")) if r["source"] == "cpsc"]
    df = json.load(open("data/word_df.json"))
    learned = json.load(open("results/learned_eval.json"))
    matcher = Matcher(recalls, word_df=df)

    items = []
    for it in matcher.items:
        r = it.recall
        items.append({
            "id": r["id"], "date": r["date"], "title": r["title"], "url": r["url"], "image": r["image"],
            "hazard": r["hazard"], "remedy": r["remedy"], "units": r["units"],
            "products": [p["name"] for p in r["products"]][:4],
            "b": sorted(it.brands), "p": [sorted(ws) for ws in it.products], "m": sorted(it.models),
            "a": sorted(it.accessory_words),
        })
    # only the words recall products actually use need a frequency
    used = {w for it in matcher.items for ws in it.products for w in ws} | {b for it in matcher.items for b in it.brands}
    # order exports have the ASIN but not the model number; for listings from
    # recalled brands that are in the catalog sample, fill it in
    asins = {}
    for line in open("data/amazon/candidates.jsonl"):
        row = json.loads(line)
        d = {k.strip().lower(): v for k, v in row["details"].items()}
        model = d.get("item model number") or d.get("model number") or ""
        if model and model.lower() not in row["title"].lower():
            asins[row["asin"]] = model
    index = {
        "recalls": items,
        "df": {w: v for w, v in df.items() if w in used},
        "asins": asins,
        "model": {"features": FEATURES, "weights": learned["weights"], "intercept": learned["intercept"],
                  "cutoff": learned["cutoff"], "maybe": 0.5},
        "built": max(r["date"] for r in recalls),
    }
    out = Path("web/public/index.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, separators=(",", ":")))
    print(f"{len(items)} recalls -> {out} ({out.stat().st_size // 1024} KB)")

    # parity fixture: labeled titles plus ordinary ones
    titles = [f"{i['title']} {i['model']}".strip() for i in load_labeled().values()]
    ordinary = [json.loads(l) for l in open("data/amazon/sample.jsonl")]
    random.Random(3).shuffle(ordinary)
    titles += [r["title"] for r in ordinary[:300]]
    w, b = learned["weights"], learned["intercept"]
    import math

    expected = []
    for t in titles:
        cands = matcher.candidates(t)
        if not cands:
            expected.append(None)
            continue
        m = cands[0]
        z = b + sum(w[f] * m.features[f] for f in FEATURES)
        p = 1 / (1 + math.exp(-z))
        expected.append({"id": m.recall["id"], "prob": round(p, 4)})
    fixture = Path("web/src/lib/__fixtures__/parity.json")
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(json.dumps({"titles": titles, "expected": expected}))
    print(f"{len(titles)} titles -> {fixture}")


if __name__ == "__main__":
    main()
