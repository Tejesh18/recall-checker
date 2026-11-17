# Labeling rule

Each row pairs a real Amazon listing with a recall it might be. The label answers one question: **if you bought this listing, would this recall apply to you?**

`1` when the listing is the recalled product line and product type: same brand, same named product (or a model number the recall lists). Colors, sizes, licensed prints and bundles that include the recalled item still count.

`0` otherwise. The cases that come up again and again:

| Looks like a match, but isn't | Example |
|---|---|
| Same brand, different product | Any Hallmark ornament vs. the Cad Bane ornament recall |
| Same product family, the one item not recalled | Thermos Stainless King *travel tumbler* vs. the Stainless King *food jar* recall |
| An accessory or spare part for the recalled product | A replacement power adapter for the Rock 'n Play soother; a Graco playard sheet; a car-seat adapter for the Armadillo Flip stroller |
| A different size or version the recall excludes | AstroAI 6-liter fridge vs. the 4-liter recall; Little Tikes *blue* swing vs. the *pink* recall |
| Shares a word, not a product | Edsal plastic bins vs. Edsal shelving |

When the recall notice doesn't settle it (it doesn't say whether a model or version is included), the label is `0`. A missed recall is bad, but telling someone their product is recalled when it isn't is how a tool like this loses trust, so ambiguity goes to "no".

## Ordinary listings

`data/amazon/sample.jsonl` is a random 1% of the listings that didn't come near any recall (no brand-plus-product-words or model-number overlap). They're treated as `0` without being read one by one. That's an assumption, not a check: a few could be recalled products listed under an unexpected brand name, which would make the false-alarm numbers slightly pessimistic.
