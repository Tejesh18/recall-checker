"""Which filter rule is flagging so many listings as candidates?"""

import collections
import json
import sys

sys.path.insert(0, "scripts")
from amazon_candidates import brand_keys, norm, recall_index  # noqa: E402

brands, names = recall_index()
by_brand, by_name = collections.Counter(), collections.Counter()
for line in open("data/amazon/candidates.jsonl").readlines()[:3000]:
    r = json.loads(line)
    hit = brand_keys(r["store"]) & brands
    if hit:
        by_brand[sorted(hit)[0]] += 1
        continue
    t = norm(r["title"])
    for n, _ in names:
        if len(n) > 12 and n in t:
            by_name[n] += 1
            break
print("brand hits", sum(by_brand.values()), by_brand.most_common(15))
print("name hits", sum(by_name.values()), by_name.most_common(8))
print("brands:", len(brands))
