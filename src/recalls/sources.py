"""Download recalls from the agencies and put them in one shape.

CPSC  consumer products (cribs, chargers, dressers, heaters...)
FDA   food, drugs and medical devices (openFDA enforcement reports)

Everything is cached under data/raw, so re-running only fetches what's new.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import httpx

RAW = Path("data/raw")
CPSC_URL = "https://www.saferproducts.gov/RestWebServices/Recall"
FDA_URL = "https://api.fda.gov/{kind}/enforcement.json"


@dataclass
class Product:
    name: str
    model: str = ""
    upcs: list[str] = field(default_factory=list)


@dataclass
class Recall:
    id: str
    source: str  # cpsc | fda-food | fda-drug | fda-device
    date: str
    title: str
    products: list[Product]
    brands: list[str]
    hazard: str
    remedy: str
    url: str
    sold_at: list[str]
    units: str = ""
    image: str = ""
    description: str = ""
    models: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _get(url: str, params: dict, cache: Path) -> object:
    if cache.exists():
        return json.loads(cache.read_text())
    resp = httpx.get(url, params=params, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(resp.text)
    return resp.json()


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


# Model numbers are 4+ characters mixing letters and digits ("A2131", "CK-10",
# "2061234X"). CPSC's structured Model field is almost always empty; they're
# written into the description instead ("model numbers 2061234 and ...").
_MODEL = re.compile(r"(?<![A-Za-z0-9-])(?=[A-Za-z0-9-]*[0-9])[A-Za-z0-9][A-Za-z0-9-]{3,}(?![A-Za-z0-9-])")
_NOT_MODELS = re.compile(r"^(?:19|20)[0-9]{2}$|^[0-9]{1,3}(?:-[0-9]{1,3})?$|^[0-9]+(?:st|nd|rd|th|s)$", re.I)


def model_numbers(text: str) -> list[str]:
    found = []
    for m in _MODEL.findall(text):
        if _NOT_MODELS.match(m) or m.isdigit() and len(m) < 5:
            continue  # years, small numbers, "1990s"
        if m.upper() not in found:
            found.append(m.upper())
    return found


def cpsc(year: int) -> list[Recall]:
    # The current year is never cached for good: new recalls land every week.
    cache = RAW / f"cpsc_{year}.json"
    if year == date.today().year and cache.exists():
        cache.unlink()
    rows = _get(CPSC_URL, {"format": "json", "RecallDateStart": f"{year}-01-01", "RecallDateEnd": f"{year}-12-31"}, cache)
    out = []
    for r in rows:
        upcs = [u["UPC"] for u in r.get("ProductUPCs") or [] if u.get("UPC")]
        products = [
            Product(_clean(p.get("Name")), _clean(p.get("Model")), upcs) for p in r.get("Products") or [] if p.get("Name")
        ]
        brands = sorted({_clean(m["Name"]) for key in ("Manufacturers", "Importers", "Distributors")
                         for m in r.get(key) or [] if m.get("Name")})
        out.append(Recall(
            id=f"cpsc-{r['RecallNumber']}",
            source="cpsc",
            date=r["RecallDate"][:10],
            title=_clean(r["Title"]),
            products=products,
            brands=brands,
            hazard="; ".join(_clean(h["Name"]) for h in r.get("Hazards") or []),
            remedy="; ".join(_clean(x["Name"]) for x in r.get("Remedies") or []),
            url=r["URL"],
            sold_at=[_clean(x["Name"]) for x in r.get("Retailers") or [] if x.get("Name")],
            units=_clean((r.get("Products") or [{}])[0].get("NumberOfUnits")),
            image=((r.get("Images") or [{}])[0] or {}).get("URL", ""),
            description=_clean(r.get("Description")),
            models=model_numbers(" ".join([_clean(r.get("Description"))] + [p.model for p in products])),
        ))
    return out


def fda(kind: str, year: int) -> list[Recall]:
    """kind: food | drug | device. openFDA pages at 1000 results."""
    out, skip = [], 0
    while True:
        cache = RAW / f"fda_{kind}_{year}_{skip}.json"
        if year == date.today().year and cache.exists():
            cache.unlink()
        try:
            page = _get(FDA_URL.format(kind=kind),
                        {"search": f"report_date:[{year}0101 TO {year}1231]", "limit": 1000, "skip": skip}, cache)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:  # openFDA answers 404 for "no results"
                break
            raise
        for r in page["results"]:
            out.append(Recall(
                id=f"fda-{kind}-{r['recall_number']}",
                source=f"fda-{kind}",
                date=f"{r['report_date'][:4]}-{r['report_date'][4:6]}-{r['report_date'][6:]}",
                title=_clean(r["product_description"])[:200],
                products=[Product(_clean(r["product_description"]), _clean(r.get("code_info"))[:300])],
                brands=[_clean(r.get("recalling_firm"))],
                hazard=_clean(r.get("reason_for_recall")),
                remedy=_clean(r.get("voluntary_mandated")),
                url=f"https://www.accessdata.fda.gov/scripts/ires/index.cfm",
                sold_at=[],
                units=_clean(r.get("product_quantity")),
            ))
        skip += 1000
        if skip >= page["meta"]["results"]["total"] or skip >= 25000:
            break
    return out
