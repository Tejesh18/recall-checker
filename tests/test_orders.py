import pytest

from recalls.orders import read_orders

AMAZON = """﻿Website,Order ID,Order Date,Purchase Order Number,Currency,Unit Price,ASIN,Quantity,Product Name
Amazon.com,111-1,2024-03-02T18:21:04Z,Not Applicable,USD,29.99,B0ABC12345,1,"Fisher-Price Baby Bouncer, Pink"
Amazon.com,111-1,2024-03-02T18:21:04Z,Not Applicable,USD,29.99,B0ABC12345,1,"Fisher-Price Baby Bouncer, Pink"
Amazon.com,111-2,2025-01-10T09:00:00Z,Not Applicable,USD,12.50,B0XYZ67890,2,USB-C Charger 20W
"""


def test_amazon_export():
    items = read_orders(AMAZON)
    assert [i.name for i in items] == ["Fisher-Price Baby Bouncer, Pink", "USB-C Charger 20W"]
    assert items[0].date == "2024-03-02"
    assert items[0].asin == "B0ABC12345"
    assert items[1].quantity == 2


def test_generic_list():
    items = read_orders("Item,Date\nSpace heater,2023-12-01\nBaby gate,\n")
    assert [(i.name, i.date) for i in items] == [("Space heater", "2023-12-01"), ("Baby gate", "")]


def test_no_name_column():
    with pytest.raises(ValueError):
        read_orders("Order ID,Total\n1,20\n")
