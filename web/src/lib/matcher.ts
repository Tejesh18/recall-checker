// Port of src/recalls/match.py. The Python side does the slow part once
// (brands, product word sets, model numbers per recall) and exports it;
// this file only has to look at the shopper's titles.
// parity.test.ts checks it against what Python decides for 649 titles.

export interface Recall {
  id: string;
  date: string;
  title: string;
  url: string;
  image: string;
  hazard: string;
  remedy: string;
  units: string;
  products: string[];
  b: string[]; // brand variants
  p: string[][]; // distinctive words of each product
  m: string[]; // model numbers
  a: string[]; // accessory words in the recalled product's own name
}

export interface Index {
  recalls: Recall[];
  df: Record<string, number>;
  asins: Record<string, string>; // ASIN -> model number, for listings from recalled brands
  model: { features: string[]; weights: Record<string, number>; intercept: number; cutoff: number; maybe: number };
  built: string;
}

export interface Candidate {
  recall: Recall;
  score: number;
  prob: number;
  why: string[];
  features: Record<string, number>;
}

const BRAND_WINDOW = 6;
const ACCESSORY = new Set(
  "replacement adapter adaptor charger cord compatible refill refills filter insert liner accessory accessories decal sticker stickers protector gasket".split(" "),
);
const MAYBE_ACCESSORY = new Set("bag bags sheet sheets cover covers case tray mount part parts pump".split(" "));

export function norm(s: string): string {
  return (s || "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").trim();
}

function tokensOf(s: string): string[] {
  return norm(s).split(/ +/).filter(Boolean);
}

export function stem(w: string): string {
  if (w.length > 4 && w.endsWith("ies")) return w.slice(0, -3) + "y";
  if (w.length > 3 && w.endsWith("s") && !w.endsWith("ss")) return w.slice(0, -1);
  return w;
}

export function modelTokens(s: string): Set<string> {
  const toks = (s || "").toLowerCase().match(/[a-z0-9]+(?:-[a-z0-9]+)*/g) ?? [];
  const out = new Set(toks);
  for (const t of toks) out.add(t.replaceAll("-", ""));
  return out;
}

export function accessoryWords(title: string): Set<string> {
  const tokens = tokensOf(title);
  const found = new Set(tokens.filter((t) => ACCESSORY.has(t)));
  let sawWith = false;
  for (const w of tokens) {
    // "sheet for Pack 'n Play" is an accessory, "blower kit with leaf bag" isn't
    if (MAYBE_ACCESSORY.has(w) && !sawWith) found.add(w);
    if (w === "with") sawWith = true;
  }
  return found;
}

export class Matcher {
  private index: Index;
  private byBrand = new Map<string, number[]>();
  private accessory: Set<string>[];

  constructor(index: Index) {
    this.index = index;
    index.recalls.forEach((r, i) => {
      for (const b of r.b) {
        const ids = this.byBrand.get(b);
        if (ids) ids.push(i);
        else this.byBrand.set(b, [i]);
      }
    });
    this.accessory = index.recalls.map((r) => new Set(r.a));
  }

  get cutoff(): number {
    return this.index.model.cutoff;
  }

  private dfOf(w: string): number {
    return this.index.df[w] ?? 0;
  }

  private weight(w: string): number {
    // rarer words in everyday listings say more about which product this is
    return -Math.log(Math.max(this.dfOf(w), 1e-5));
  }

  private prob(features: Record<string, number>): number {
    const { features: names, weights, intercept } = this.index.model;
    let z = intercept;
    for (const f of names) z += weights[f] * features[f];
    return 1 / (1 + Math.exp(-z));
  }

  candidates(title: string): Candidate[] {
    const tokens = tokensOf(title);
    const tw = new Set(tokens.map(stem));
    const mt = modelTokens(title);
    const window = tokens.slice(0, BRAND_WINDOW);
    const head = " " + window.join(" ") + " ";

    // longest brand first, then earliest, so "little tikes" beats "little"
    const found = new Map<number, string>();
    for (let n = window.length; n > 0; n--) {
      for (let s = 0; s + n <= window.length; s++) {
        const b = window.slice(s, s + n).join(" ");
        for (const i of this.byBrand.get(b) ?? []) if (!found.has(i)) found.set(i, b);
      }
    }

    const accessory = accessoryWords(title);
    const out: Candidate[] = [];
    for (const [i, brand] of found) {
      const r = this.index.recalls[i];
      const own = this.accessory[i];
      if ([...accessory].some((w) => !own.has(w))) continue; // a charger for it, not it

      const why = [`brand: ${brand}`];
      let score = 0;
      const models = r.m.filter((m) => mt.has(m) || mt.has(m.replaceAll("-", ""))).sort();
      if (models.length) {
        score += 3;
        why.push(`model number ${models[0].toUpperCase()}`);
      }
      let best = 0;
      let bestShared: string[] = [];
      for (const pw of r.p) {
        let total = 0;
        for (const w of pw) total += this.weight(w);
        const shared = pw.filter((w) => tw.has(w));
        let got = 0;
        for (const w of shared) got += this.weight(w);
        const cov = total ? got / total : 0;
        if (cov > best && shared.length >= Math.min(2, pw.length)) {
          best = cov;
          bestShared = shared;
        }
      }
      if (best >= 0.5) {
        score += 3 * best;
        why.push(`${Math.round(best * 100)}% of the product name: ${[...bestShared].sort().slice(0, 4).join(", ")}`);
      }
      const common = !brand.includes(" ") && this.dfOf(brand) > 0.001;
      if (common && !models.length) score -= 1;

      const features = {
        model: models.length ? 1 : 0,
        coverage: best,
        shared: bestShared.length,
        rare_shared: bestShared.filter((w) => this.dfOf(w) < 0.001).length,
        common_brand: common ? 1 : 0,
        brand_words: brand.split(" ").length,
        brand_at_start: head.startsWith(` ${brand} `) ? 1 : 0,
        title_words: tokens.length,
        products_in_recall: r.p.length,
      };
      out.push({ recall: r, score, prob: this.prob(features), why, features });
    }
    return out.sort((x, y) => y.score - x.score || (x.recall.id < y.recall.id ? -1 : x.recall.id > y.recall.id ? 1 : 0));
  }

  // the best candidate, if the learned model is confident enough
  match(title: string): Candidate | null {
    const top = this.candidates(title)[0];
    return top && top.prob >= this.cutoff ? top : null;
  }

  // An order export has the title and ASIN but no model number. If we know the
  // ASIN's model number from the catalog, add it, the way the model was trained.
  check(name: string, asin = ""): Verdict {
    const model = this.index.asins[asin.trim().toUpperCase()];
    const top = this.candidates(model ? `${name} ${model}` : name)[0];
    if (!top || top.prob < this.index.model.maybe) return { kind: "clear" };
    if (model) top.why.push(`model number from the listing: ${model}`);
    return { kind: top.prob >= this.cutoff ? "recalled" : "maybe", match: top };
  }
}

export type Verdict = { kind: "clear" } | { kind: "recalled" | "maybe"; match: Candidate };
