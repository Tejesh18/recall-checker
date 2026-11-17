"""Export what the website needs to match in the browser.

web/public/index.json   recalls, already broken into the pieces the matcher
                        uses (brands, product word sets, model numbers), plus
                        word frequencies, ASIN -> model numbers and the
                        learned weights. Rebuilt every day by the deploy job.

With --fixture, also freezes a copy for the TypeScript tests:
web/src/lib/__fixtures__/index.json and parity.json (titles and what the
Python matcher decides for them). Needs the Amazon sample in data/amazon.

    python -m recalls.export [--fixture]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
from pathlib import Path

from .evaluate import load_labeled
from .learned import FEATURES
from .match import Matcher

ASINS = Path("data/asins.json")


def asin_models() -> dict[str, str]:
    """Order exports have the ASIN but not the model number. For listings from
    recalled brands in the catalog sample, keep the model number. The sample
    isn't in git, so the result is (data/asins.json is)."""
    src = Path("data/amazon/candidates.jsonl")
    if not src.exists():
        return json.loads(ASINS.read_text())
    asins = {}
    for line in open(src):
        row = json.loads(line)
        d = {k.strip().lower(): v for k, v in row["details"].items()}
        model = d.get("item model number") or d.get("model number") or ""
        if model and model.lower() not in row["title"].lower():
            asins[row["asin"]] = model
    ASINS.write_text(json.dumps(asins, sort_keys=True, indent=0))
    return asins


def build_index(matcher: Matcher, recalls: list[dict], df: dict, learned: dict) -> dict:
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
    return {
        "recalls": items,
        "df": {w: v for w, v in df.items() if w in used},
        "asins": asin_models(),
        "model": {"features": FEATURES, "weights": learned["weights"], "intercept": learned["intercept"],
                  "cutoff": learned["cutoff"], "maybe": 0.5},
        "built": max(r["date"] for r in recalls),
    }


def write_fixture(matcher: Matcher, learned: dict, index_path: Path) -> None:
    titles = [f"{i['title']} {i['model']}".strip() for i in load_labeled().values()]
    ordinary = [json.loads(l) for l in open("data/amazon/sample.jsonl")]
    random.Random(3).shuffle(ordinary)
    titles += [r["title"] for r in ordinary[:300]]
    w, b = learned["weights"], learned["intercept"]
    expected = []
    for t in titles:
        cands = matcher.candidates(t)
        if not cands:
            expected.append(None)
            continue
        m = cands[0]
        p = 1 / (1 + math.exp(-(b + sum(w[f] * m.features[f] for f in FEATURES))))
        expected.append({"id": m.recall["id"], "prob": round(p, 4)})
    out = Path("web/src/lib/__fixtures__")
    out.mkdir(parents=True, exist_ok=True)
    (out / "parity.json").write_text(json.dumps({"titles": titles, "expected": expected}))
    shutil.copy(index_path, out / "index.json")
    print(f"{len(titles)} titles -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    args = ap.parse_args()

    recalls = [r for r in json.load(open("data/recalls.json")) if r["source"] == "cpsc"]
    df = json.load(open("data/word_df.json"))
    learned = json.load(open("results/learned_eval.json"))
    matcher = Matcher(recalls, word_df=df)

    out = Path("web/public/index.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_index(matcher, recalls, df, learned), separators=(",", ":")))
    print(f"{len(matcher.items)} recalls -> {out} ({out.stat().st_size // 1024} KB)")
    if args.fixture:
        write_fixture(matcher, learned, out)


if __name__ == "__main__":
    main()
