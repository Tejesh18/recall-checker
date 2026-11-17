import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { Matcher, accessoryWords, modelTokens, stem, type Index } from "./matcher";
import { readOrders } from "./orders";
import parity from "./__fixtures__/parity.json";

const index: Index = JSON.parse(readFileSync(new URL("../../public/index.json", import.meta.url), "utf8"));
const matcher = new Matcher(index);

describe("matcher", () => {
  it("agrees with the Python matcher on every fixture title", () => {
    const wrong: string[] = [];
    parity.titles.forEach((title: string, i: number) => {
      const want = parity.expected[i] as { id: string; prob: number } | null;
      const got = matcher.candidates(title)[0];
      if (!want) {
        if (got) wrong.push(`${title}: expected nothing, got ${got.recall.id}`);
      } else if (!got || got.recall.id !== want.id || Math.abs(got.prob - want.prob) > 1e-3) {
        wrong.push(`${title}: expected ${want.id} ${want.prob}, got ${got?.recall.id} ${got?.prob}`);
      }
    });
    expect(wrong).toEqual([]);
  });

  it("finds the recalled things in the sample order history and nothing else", () => {
    const csv = readFileSync(new URL("../../public/sample-orders.csv", import.meta.url), "utf8");
    const verdicts = readOrders(csv).map((o) => ({ name: o.name.split(" ").slice(0, 3).join(" "), v: matcher.check(o.name, o.asin) }));
    // "thermos" is an everyday word, so even with the model number it's only "worth checking"
    expect(verdicts.filter((x) => x.v.kind === "maybe").map((x) => x.name)).toEqual(["THERMOS Stainless King"]);
    expect(verdicts.filter((x) => x.v.kind === "recalled").map((x) => x.name)).toEqual([
      "Secura Digital Air",
      "Mueller Pro Series",
      "BISSELL Multi Reach",
      "Fisher-Price Teething &",
    ]);
  });

  it("keeps hyphens and drops them in model numbers", () => {
    expect(modelTokens("Secura TXG-DS16 air fryer")).toContain("txgds16");
    expect(modelTokens("Secura TXG-DS16 air fryer")).toContain("txg-ds16");
  });

  it("stems plurals", () => {
    expect(stem("carriers")).toBe("carrier");
    expect(stem("batteries")).toBe("battery");
    expect(stem("glass")).toBe("glass");
  });

  it("only counts bag/sheet/cover as accessories before 'with'", () => {
    expect(accessoryWords("Fitted sheet for Pack n Play")).toContain("sheet");
    expect(accessoryWords("Leaf blower kit with bag")).not.toContain("bag");
  });
});

describe("orders", () => {
  it("reads an Amazon export and drops repeat shipments", () => {
    const csv =
      '﻿"Website","Order ID","Order Date","Quantity","ASIN","Product Name"\r\n' +
      '"Amazon.com","1","2024-03-01T10:00:00Z","2","B0X","Kids Helmet, Blue"\r\n' +
      '"Amazon.com","1","2024-03-01T10:00:00Z","2","B0X","Kids Helmet, Blue"\r\n' +
      '"Amazon.com","2","2024-05-09T10:00:00Z","1","B0Y","Space heater ""1500W"""\r\n';
    const orders = readOrders(csv);
    expect(orders).toHaveLength(2);
    expect(orders[0]).toEqual({ name: "Kids Helmet, Blue", date: "2024-03-01", asin: "B0X", quantity: 2 });
    expect(orders[1].name).toBe('Space heater "1500W"');
  });

  it("takes any CSV with a name-like column", () => {
    expect(readOrders("Item,Price\nToaster,20\n").map((o) => o.name)).toEqual(["Toaster"]);
  });

  it("says so when there's no product column", () => {
    expect(() => readOrders("a,b\n1,2\n")).toThrow(/product name/);
  });
});
