from recalls.match import Matcher

RECALLS = [
    {
        "id": "cpsc-1",
        "title": "Secura Recalls Air Fryers Due to Fire and Burn Hazards",
        "brands": ["Secura Inc."],
        "products": [{"name": "Secura Digital Air Fryers"}],
        "models": ["SAF-53D"],
    },
    {
        "id": "cpsc-2",
        "title": "BISSELL Recalls Multi Reach Hand and Floor Vacuum Cleaners",
        "brands": ["BISSELL"],
        "products": [{"name": "Multi Reach Hand and Floor Vacuums"}],
        "models": ["2151A"],
    },
]
DF = {"air": 0.01, "fryer": 0.002, "digital": 0.02, "multi": 0.005, "reach": 0.001, "hand": 0.01,
      "floor": 0.01, "vacuum": 0.003}


def top(title):
    c = Matcher(RECALLS, word_df=DF).candidates(title)
    return c[0] if c else None


def test_model_number_without_hyphen():
    m = top("Secura SAF53D 5.3 Qt Air Fryer")
    assert m.recall["id"] == "cpsc-1"
    assert m.features["model"] == 1.0


def test_brand_has_to_be_near_the_start():
    assert top("Air fryer liners, 100 pack, fits Ninja Cosori Instant Gowise Secura") is None


def test_accessory_for_the_product_is_not_the_product():
    assert top("BISSELL Replacement Charger for Multi Reach 2151A") is None


def test_same_brand_other_product_has_low_coverage():
    m = top("BISSELL CleanView Swivel Pet Upright Vacuum")
    assert m.features["model"] == 0.0
    assert m.features["coverage"] < 0.5
