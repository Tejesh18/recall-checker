import { unzipSync, strFromU8 } from "fflate";

// Amazon sends the data as a zip ("Your Orders.zip") with the order history
// somewhere inside. Take the zip or the csv, whichever people drop.
export async function readOrderFile(file: File): Promise<string> {
  if (!file.name.toLowerCase().endsWith(".zip")) return file.text();
  const files = unzipSync(new Uint8Array(await file.arrayBuffer()), {
    filter: (f) => f.name.toLowerCase().endsWith(".csv"),
  });
  const names = Object.keys(files);
  const pick = names.find((n) => /orderhistory/i.test(n)) ?? names[0];
  if (!pick) throw new Error("That zip doesn't have a CSV in it. Look for Retail.OrderHistory.1.csv.");
  return strFromU8(files[pick]);
}
