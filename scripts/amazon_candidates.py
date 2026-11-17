"""Pull real Amazon listings to test the matcher on.

Streams product metadata from the Amazon Reviews 2023 dataset (McAuley Lab,
UCSD) category by category, without saving the multi-GB files, and keeps:

  candidates.jsonl  listings whose brand has had a CPSC recall, or whose
                    title contains a recalled product's name. Some of these
                    are the recalled product; most are not. Deciding which
                    is the labeling job.
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


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


def brand_keys(name: str) -> set[str]:
    words = [w for w in norm(name).split() if w not in GENERIC and len(w) > 2]
    return {" ".join(words)} if words else set()


def recall_index() -> tuple[set[str], list[tuple[str, str]]]:
    recalls = [r for r in json.loads(Path("data/recalls.json").read_text()) if r["source"] == "cpsc"]
    brands: set[str] = set()
    names: list[tuple[str, str]] = []
    for r in recalls:
        for b in r["brands"]:
            brands |= brand_keys(b)
        for p in r["products"]:
            n = norm(p["name"])
            if len(n.split()) >= 3:
                names.append((n, r["id"]))
        # titles usually start with the brand: "17 Stories Furniture 18-Drawer Dressers Recalled ..."
        head = norm(r["title"].split(" Recall")[0])
        if head:
            brands.add(" ".join(head.split()[:2]))
    return brands, names


def main(categories: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    brands, names = recall_index()
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
                t = norm(title)
                hit = bool(brand_keys(store) & brands) or any(n in t for n, _ in names if len(n) > 12)
                if hit:
                    cand.write(json.dumps(row) + "\n")
                    kept += 1
                elif rng.random() < 0.01:
                    sample.write(json.dumps(row) + "\n")
        print(f"{cat}: {seen} listings, {kept} candidates", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
