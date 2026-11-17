"""Draw the candidate pairs to label: (Amazon listing, recall it might be).

All pairs that share a model number, plus a random sample of the rest.
Writes labels/to_label.csv with an empty label column and prints a compact
view to label from.
"""

import csv
import json
import random
import re
import sys
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
recalls = {r["id"]: r for r in json.load(open("data/recalls.json"))}
cands = [json.loads(l) for l in open("data/amazon/candidates.jsonl")]
rng = random.Random(11)


def listing_models(row):
    text = " ".join([row["title"], *map(str, row["details"].values())]).upper()
    return set(re.findall(r"[A-Z0-9][A-Z0-9-]{3,}", text))


pairs = []
for c in cands:
    for rid in c["recall_ids"]:
        shared = sorted(listing_models(c) & set(recalls[rid]["models"]))
        pairs.append((c, rid, shared))

with_model = [p for p in pairs if p[2]]
rest = [p for p in pairs if not p[2]]
chosen = with_model + rng.sample(rest, min(N, len(rest)))
rng.shuffle(chosen)

Path("labels").mkdir(exist_ok=True)
with open("labels/to_label.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["pair_id", "asin", "category", "listing_title", "listing_model", "recall_id", "recall_title",
                "recall_products", "shared_model", "label"])
    for i, (c, rid, shared) in enumerate(chosen):
        r = recalls[rid]
        model = c["details"].get("Item model number") or c["details"].get("Model Name") or ""
        products = " | ".join(p["name"] for p in r["products"])[:200]
        w.writerow([i, c["asin"], c["category"], c["title"][:160], model, rid, r["title"][:150], products,
                    " ".join(shared), ""])
        print(f"{i}\t{c['title'][:110]} [{model}]\n\t=> {r['title'][:110]} :: {products[:110]} {('MODEL ' + ' '.join(shared)) if shared else ''}")
print(len(chosen), "pairs", file=sys.stderr)
