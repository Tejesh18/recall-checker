import type { Index } from "../lib/matcher";

export default function About({ index }: { index: Index }) {
  return (
    <section className="about">
      <h2>Why I made this</h2>
      <p>
        There were 420 consumer product recalls in 2025 and there have been 521 so far in 2026. In 2016 about one in
        four recall notices mentioned Amazon; now it's six in ten. The CPSC posts every one, but nobody reads recall
        notices for an air fryer they bought two years ago.
        Retailers do email some buyers, but not reliably, and not if you bought it somewhere else.
      </p>
      <p>
        You already have the list of what you bought. This just puts the two lists side by side.
      </p>

      <h2>How the matching works</h2>
      <p>
        Recall notices and Amazon titles describe the same product differently ("Stainless King Food Jar" vs.
        "THERMOS Stainless King Vacuum-Insulated Food Jar, 24 Ounce, Midnight Blue"), and a lot of products share a
        brand with something recalled. So a match needs the brand near the start of the title, plus either the
        model number or most of the recalled product's distinctive words. Replacement parts and accessories
        (a charger for a recalled vacuum) are left out. A small model trained on 350 hand-checked listing/recall
        pairs decides how sure to be.
      </p>
      <p>

        On those pairs, when the model number is known, it flags about two thirds of the recalled listings with no
        false alarms, and none of 2,000 random Amazon listings. From the title alone it's closer to four in ten,
        which is why it looks up model numbers by ASIN where it can. Treat a clean result as "nothing obvious", not
        a guarantee.
      </p>
      <p className="small">
        {index.recalls.length.toLocaleString()} CPSC recalls, newest from {index.built}. Data from{" "}
        <a href="https://www.cpsc.gov/Recalls" target="_blank" rel="noreferrer">
          cpsc.gov
        </a>
        . Code on{" "}
        <a href="https://github.com/Tejesh18/recall-checker" target="_blank" rel="noreferrer">
          GitHub
        </a>
        .
      </p>
    </section>
  );
}
