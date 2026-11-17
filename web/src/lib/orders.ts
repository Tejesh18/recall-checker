// Port of src/recalls/orders.py.
// Amazon's "Your Orders" export has Retail.OrderHistory.1.csv with one row per
// item. Anything else works too if it has a column that looks like a product
// name (Walmart and Target exports, a list typed into a spreadsheet).

export interface Purchase {
  name: string;
  date: string;
  asin: string;
  quantity: number;
}

const NAME_COLUMNS = ["product name", "item name", "item", "title", "product", "description", "name"];
const DATE_COLUMNS = ["order date", "date", "purchase date", "order placed"];

// RFC 4180-ish: quoted fields, doubled quotes, newlines inside quotes
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += c;
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

function find(header: string[], options: string[]): number {
  const lowered = header.map((h) => h.trim().toLowerCase());
  for (const opt of options) {
    const i = lowered.indexOf(opt);
    if (i >= 0) return i;
  }
  return -1;
}

export function readOrders(text: string): Purchase[] {
  const rows = parseCsv(text.replace(/^﻿/, ""));
  if (!rows.length) return [];
  const header = rows[0];
  const nameI = find(header, NAME_COLUMNS);
  if (nameI < 0) throw new Error(`Couldn't find a product name column. Columns were: ${header.join(", ")}`);
  const dateI = find(header, DATE_COLUMNS);
  const asinI = find(header, ["asin"]);
  const qtyI = find(header, ["quantity", "qty"]);
  const cell = (row: string[], i: number) => (i >= 0 && i < row.length ? row[i] : "");

  const seen = new Set<string>();
  const out: Purchase[] = [];
  for (const row of rows.slice(1)) {
    const name = cell(row, nameI).trim();
    if (!name) continue;
    const qty = parseFloat(cell(row, qtyI));
    const p = {
      name,
      date: cell(row, dateI).slice(0, 10),
      asin: cell(row, asinI),
      quantity: Number.isFinite(qty) ? Math.trunc(qty) : 1,
    };
    const key = `${p.asin || p.name.toLowerCase()}|${p.date}`;
    if (seen.has(key)) continue; // the same item shows up once per shipment
    seen.add(key);
    out.push(p);
  }
  return out;
}
