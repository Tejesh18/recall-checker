"""Pull real Amazon listings to test the matcher on.

Streams product metadata from the Amazon Reviews 2023 dataset (McAuley Lab,
UCSD) category by category, without saving the multi-GB files, and keeps:

  candidates.jsonl  listings from a brand with a CPSC recall that share at
                    least two distinctive words with a recalled product's
                    name, or mention a recalled model number. Brand alone is
                    useless: nearly every big baby brand has had a recall.
  sample.jsonl      a random 1% of everything else: ordinary products the
                    matcher must NOT flag.

    python scripts/amazon_candidates.py Baby_Products Toys_and_Games ...
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import httpx

BASE = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_{}.jsonl"
OUT = Path("data/amazon")
GENERIC = {"inc", "llc", "ltd", "co", "corp", "corporation", "company", "the", "usa", "us", "international",
           "products", "group", "limited", "technology", "trading", "brands", "home", "shenzhen", "industries"}

# words that appear in so many product names they say nothing about which product it is
COMMON = GENERIC | {"baby", "kids", "children", "child", "infant", "toddler", "set", "pack", "new", "for", "with",
                    "and", "black", "white", "pink", "blue", "gray", "grey", "model", "models", "series", "sold",
                    "recalled", "recall", "product", "item", "items", "size", "inch", "inches"}

# model numbers: 4+ characters mixing letters and digits, like "a2131" or "ck-10"
WB = chr(92) + "b"  # a regex word boundary, spelled out so no tool turns it into a backspace again
MODEL_RE = re.compile(WB + r"(?=[a-z0-9-]*[0-9])(?=[a-z0-9-]*[a-z])[a-z0-9-]{4,}" + WB)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


def brand_keys(name: str) -> set[str]:
    words = [w for w in norm(name).split() if w not in GENERIC and len(w) > 2]
    return {" ".join(words)} if words else set()


def recall_index():
    """For each recalled product: its brand keys, the distinctive words of its
    name, and any model numbers mentioned."""
    recalls = [r for r in json.loads(Path("data/recalls.json").read_text()) if r["source"] == "cpsc"]
    by_brand: dict[str, list[tuple[str, set[str]]]] = {}
    models: dict[str, str] = {}
    for r in recalls:
        keys: set[str] = set()
        for b in r["brands"]:
            keys |= brand_keys(b)
        head = norm(r["title"].split(" Recall")[0]).split()
        if head:
            keys.add(" ".join(head[:2]))
        brand_words = {w for k in keys for w in k.split()}
        for p in r["products"]:
            words = {w for w in norm(p["name"]).split() if w not in COMMON and w not in brand_words and len(w) > 2}
            for k in keys:
                by_brand.setdefault(k, []).append((r["id"], words))
            for m in MODEL_RE.findall(norm(p["model"])):
                models[m] = r["id"]
    return by_brand, models


def main(categories: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    by_brand, models = recall_index()
    print(f"index: {len(by_brand)} brand keys, {len(models)} model numbers", flush=True)
    rng = random.Random(7)
    cand = (OUT / "candidates.jsonl").open("a")
    sample = (OUT / "sample.jsonl").open("a")
    for cat in categories:
        kept = seen = 0
        with httpx.stream("GET", BASE.format(cat), timeout=None, follow_redirects=True) as resp:
            for line in resp.iter_lines():
                if not line:
                    continue
                seen += 1
                item = json.loads(line)
                title = item.get("title") or ""
                store = item.get("store") or ""
                row = {"asin": item.get("parent_asin"), "category": cat, "title": title, "store": store,
                       "details": {k: v for k, v in (item.get("details") or {}).items()
                                   if k in ("Item model number", "Manufacturer", "Brand", "Model Name")}}
                t = norm(title + " " + " ".join(map(str, row["details"].values())))
                words = set(t.split())
                matches = set()
                for k in brand_keys(store) | brand_keys(str(row["details"].get("Brand", ""))):
                    for rid, distinctive in by_brand.get(k, []):
                        if len(words & distinctive) >= 2:
                            matches.add(rid)
                for m in MODEL_RE.findall(t):
                    if m in models:
                        matches.add(models[m])
                if matches:
                    cand.write(json.dumps({**row, "recall_ids": sorted(matches)}) + "\n")
                    kept += 1
                elif rng.random() < 0.01:
                    sample.write(json.dumps(row) + "\n")
        print(f"{cat}: {seen} listings, {kept} candidates", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
