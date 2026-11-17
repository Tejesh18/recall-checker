"""How common is each word in ordinary Amazon titles?

Computed from the random sample of listings that never came near a recall.
The matcher uses it to tell "slimfit" (says which product this is) from
"christmas" (says nothing).

    python -m recalls.word_stats
"""

import json
from collections import Counter
from pathlib import Path

from .match import norm


def compute(path: str = "data/amazon/sample.jsonl", min_count: int = 3) -> dict[str, float]:
    n, counts = 0, Counter()
    for line in open(path):
        n += 1
        counts.update(set(norm(json.loads(line)["title"]).split()))
    return {w: round(c / n, 6) for w, c in counts.items() if c >= min_count}


def main() -> None:
    df = compute()
    out = Path("data/word_df.json")
    out.write_text(json.dumps(df))
    top = sorted(df.items(), key=lambda kv: -kv[1])[:15]
    print(f"{len(df)} words -> {out}; most common: {', '.join(w for w, _ in top)}")


if __name__ == "__main__":
    main()
