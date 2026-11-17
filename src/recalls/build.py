"""Build data/recalls.json from every source.

    python -m recalls.build --since 2016
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

from .sources import cpsc, fda


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=2016)
    ap.add_argument("--fda", action="store_true", help="also pull FDA food/drug/device recalls")
    args = ap.parse_args()

    recalls = []
    for year in range(args.since, date.today().year + 1):
        got = cpsc(year)
        if args.fda:
            for kind in ("food", "drug", "device"):
                got += fda(kind, year)
        recalls += got
        print(year, Counter(r.source for r in got), flush=True)

    out = Path("data/recalls.json")
    out.write_text(json.dumps([r.to_dict() for r in recalls]))
    print(f"{len(recalls)} recalls -> {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
