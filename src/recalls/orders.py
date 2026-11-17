"""Read an order history export into a list of purchased items.

Amazon: Account -> Request Your Data -> "Your Orders". The zip contains
Retail.OrderHistory.1.csv with one row per item, including "Product Name",
"ASIN" and "Order Date".

Anything else: any CSV with a column that looks like a product name
("Product Name", "Item", "Title", "Description"...). Walmart and Target
exports and hand-made lists all work this way.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

NAME_COLUMNS = ("product name", "item name", "item", "title", "product", "description", "name")
DATE_COLUMNS = ("order date", "date", "purchase date", "order placed")


@dataclass
class Purchase:
    name: str
    date: str = ""
    asin: str = ""
    quantity: int = 1


def _find(header: list[str], options: tuple[str, ...]) -> int | None:
    lowered = [h.strip().lower() for h in header]
    for opt in options:
        if opt in lowered:
            return lowered.index(opt)
    return None


def read_orders(text: str) -> list[Purchase]:
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        return []
    header = rows[0]
    name_i = _find(header, NAME_COLUMNS)
    if name_i is None:
        raise ValueError(f"couldn't find a product name column in: {header}")
    date_i = _find(header, DATE_COLUMNS)
    asin_i = _find(header, ("asin",))
    qty_i = _find(header, ("quantity", "qty"))

    seen: set[tuple[str, str]] = set()
    out = []
    for row in rows[1:]:
        if len(row) <= name_i or not row[name_i].strip():
            continue
        p = Purchase(
            name=row[name_i].strip(),
            date=row[date_i][:10] if date_i is not None and len(row) > date_i else "",
            asin=row[asin_i] if asin_i is not None and len(row) > asin_i else "",
            quantity=int(float(row[qty_i])) if qty_i is not None and len(row) > qty_i and row[qty_i].strip() else 1,
        )
        key = (p.asin or p.name.lower(), p.date)
        if key in seen:  # the same item appears once per shipment
            continue
        seen.add(key)
        out.append(p)
    return out
