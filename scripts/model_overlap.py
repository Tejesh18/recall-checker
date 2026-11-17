"""How many candidate listings share a model number with the recall they matched?"""

import json
import random
import re

recalls = {r["id"]: r for r in json.load(open("data/recalls.json"))}
cands = [json.loads(l) for l in open("data/amazon/candidates.jsonl")]


def listing_models(row):
    text = " ".join([row["title"], *map(str, row["details"].values())]).upper()
    return set(re.findall(r"[A-Z0-9][A-Z0-9-]{3,}", text))


hits = []
for c in cands:
    lm = listing_models(c)
    for rid in c["recall_ids"]:
        shared = lm & set(recalls[rid].get("models", []))
        shared = {m for m in shared if any(ch.isalpha() for ch in m) and any(ch.isdigit() for ch in m)}
        if shared:
            hits.append((c, rid, sorted(shared)))
print(len(cands), "candidates;", len(hits), "share a model number with their recall")
random.seed(1)
for c, rid, shared in random.sample(hits, min(12, len(hits))):
    print(f"- {c['title'][:85]}\n    -> {recalls[rid]['title'][:85]} | {shared[:3]}")
