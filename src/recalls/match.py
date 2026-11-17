"""Match a purchased item to recalls.

v0 (brand + any shared word) caught 60 of 61 recalled listings, but 82% of
its alerts were wrong and it flagged 1 in 5 ordinary products. Three causes,
three fixes:

1. Loose brands. Single everyday words ("Comfort", "Home") counted as brands
   anywhere in the title. Now a brand has to appear in the first few words of
   the title, where Amazon puts it, and a one-word brand that's also a common
   word in ordinary listings isn't enough on its own.
2. Weak evidence. Sharing "christmas" or "digital" with a recall meant
   nothing. Word weights now come from how common a word is across ordinary
   Amazon titles, and a match needs most of the recalled product's
   distinctive words, not just one.
3. Accessories. A replacement charger or a playard sheet carries the
   recalled product's name and even its model number. Titles that are
   clearly an accessory for something are rejected unless the recall itself
   is about that accessory.

Two stages: retrieve recalls whose brand is in the title, then score each on
model numbers and name coverage, and keep the best one over a threshold.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

GENERIC = {"inc", "llc", "ltd", "co", "corp", "corporation", "company", "the", "usa", "us", "international",
           "products", "group", "limited", "technology", "trading", "brands", "home", "shenzhen", "industries",
           "manufacturing", "enterprises", "holdings", "global", "store", "official"}
STOP = GENERIC | {"for", "with", "and", "of", "in", "to", "a", "an", "by", "on", "set", "pack", "new", "sold", "recalled",
                  "recall", "recalls", "due", "hazard", "risk", "model", "models", "item", "items", "size", "or"}
# words that make a listing an accessory for something rather than the thing
ACCESSORY = {"replacement", "adapter", "adaptor", "charger", "cord", "compatible", "refill", "refills", "filter",
             "insert", "liner", "accessory", "accessories", "decal", "sticker", "stickers", "protector", "gasket"}
# ...and words that only do when the listing IS that thing, not when it comes WITH one
# ("sheet for Pack 'n Play" is an accessory; "blower kit with leaf bag" isn't)
MAYBE_ACCESSORY = {"bag", "bags", "sheet", "sheets", "cover", "covers", "case", "tray", "mount", "part", "parts", "pump"}
BRAND_WINDOW = 6  # brands appear in the first few words of an Amazon title


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


def stem(w: str) -> str:
    # enough to make "carriers"/"carrier" and "panels"/"panel" agree
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def words(s: str) -> list[str]:
    return [stem(w) for w in norm(s).split() if w not in STOP and len(w) > 1]


def model_tokens(s: str) -> set[str]:
    """'Secura TXG-DS16 air fryer' -> {'txg-ds16', 'txgds16', ...}: hyphens kept and dropped."""
    toks = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", (s or "").lower())
    return set(toks) | {t.replace("-", "") for t in toks}


def accessory_words(title: str) -> set[str]:
    tokens = norm(title).split()
    found = set(tokens) & ACCESSORY
    for i, w in enumerate(tokens):
        # a "maybe" word counts unless the title says the product comes WITH it
        if w in MAYBE_ACCESSORY and "with" not in tokens[:i]:
            found.add(w)
    return found


def brand_variants(name: str) -> set[str]:
    ws = [w for w in norm(name).split() if w not in GENERIC]
    out = set()
    if ws:
        out.add(" ".join(ws))
        if len(ws[0]) >= 4:
            out.add(ws[0])
    return out


@dataclass
class Indexed:
    recall: dict
    brands: set[str]
    products: list[set[str]]  # distinctive words of each product in the recall
    models: set[str]
    accessory_words: set[str]


@dataclass
class Match:
    recall: dict
    score: float
    reasons: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)


class Matcher:
    """word_df: share of ordinary Amazon titles containing each word
    (see recalls.build_index). Common words carry little weight."""

    def __init__(self, recalls: list[dict], word_df: dict[str, float] | None = None, threshold: float = 2.0,
                 min_coverage: float = 0.5):
        self.threshold = threshold
        self.min_coverage = min_coverage
        self.df = word_df or {}
        self.items: list[Indexed] = []
        self.by_brand: dict[str, list[int]] = {}
        for r in recalls:
            brands = set()
            for b in r["brands"]:
                brands |= brand_variants(b)
            head = norm(r["title"].split(" Recall")[0]).split()
            if head:
                brands.add(head[0] if len(head[0]) >= 4 else " ".join(head[:2]))
            brand_words = {stem(w) for b in brands for w in b.split()}
            names = " ".join(p["name"] for p in r["products"])
            # one recall often covers several products ("Stainless King 3000 and 3020
            # Food Jars and Sportsman 3010 Bottles"); score each separately
            parts = [x for p in r["products"] for x in re.split(r"\band\b|,|;|/", p["name"])]
            whole = {w for w in words(names) if w not in brand_words}
            # pieces need two distinctive words: "3020" alone matches far too easily
            products = [ws for ws in ({w for w in words(x) if w not in brand_words} for x in parts) if len(ws) >= 2]
            if whole and whole not in products:
                products.append(whole)
            idx = len(self.items)
            self.items.append(Indexed(r, brands, products, {m.lower() for m in r.get("models", [])},
                                      accessory_words(names)))
            for b in brands:
                self.by_brand.setdefault(b, []).append(idx)

    def weight(self, w: str) -> float:
        # rarer words in everyday listings say more about which product this is
        return -math.log(max(self.df.get(w, 0.0), 1e-5))

    def _is_common_word(self, brand: str) -> bool:
        return " " not in brand and self.df.get(brand, 0.0) > 0.001

    def candidates(self, title: str) -> list[Match]:
        t = norm(title)
        tokens = t.split()
        tw = {stem(w) for w in tokens}
        mt = model_tokens(title)
        head = " " + " ".join(tokens[:BRAND_WINDOW]) + " "
        window = tokens[:BRAND_WINDOW]
        found: dict[int, str] = {}
        # longest brand first, then earliest, so "little tikes" beats "little"
        for n in range(len(window), 0, -1):
            for s in range(len(window) - n + 1):
                for i in self.by_brand.get(" ".join(window[s:s + n]), ()):
                    found.setdefault(i, " ".join(window[s:s + n]))
        accessory = accessory_words(title)
        out = []
        for i, brand in found.items():
            it = self.items[i]
            reasons, score = [f"brand {brand}"], 0.0
            if accessory - it.accessory_words:
                continue  # a charger/sheet/adapter for the product, not the product
            models = sorted(m for m in it.models if m in mt or m.replace("-", "") in mt)
            if models:
                score += 3.0
                reasons.append(f"model {models[0].upper()}")
            best, best_shared = 0.0, []
            for pw in it.products:
                pw = sorted(pw)
                total = sum(self.weight(w) for w in pw)
                shared = [w for w in pw if w in tw]
                cov = sum(self.weight(w) for w in shared) / total if total else 0.0
                if cov > best and len(shared) >= min(2, len(pw)):
                    best, best_shared = cov, shared
            if best >= self.min_coverage:
                score += 3.0 * best
                reasons.append(f"{best:.0%} of the product name: {', '.join(sorted(best_shared)[:4])}")
            common = self._is_common_word(brand)
            if common and not models:
                score -= 1.0  # "Comfort" or "Home" as a brand needs more than words
            features = {
                "model": float(bool(models)),
                "coverage": best,
                "shared": float(len(best_shared)),
                "rare_shared": float(sum(1 for w in best_shared if self.df.get(w, 0) < 0.001)),
                "common_brand": float(common),
                "brand_words": float(len(brand.split())),
                "brand_at_start": float(head.startswith(f" {brand} ")),
                "title_words": float(len(tokens)),
                "products_in_recall": float(len(it.products)),
            }
            out.append(Match(it.recall, score, reasons, features))
        return sorted(out, key=lambda m: (-m.score, str(m.recall["id"])))

    def match(self, title: str) -> Match | None:
        cands = self.candidates(title)
        if cands and cands[0].score >= self.threshold:
            return cands[0]
        return None
