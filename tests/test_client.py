"""เทสต์ parse_response — ป้อน JSON ตัวอย่าง ไม่ยิงเน็ตจริง."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poe_price.client import parse_response

# จำลองรูปร่าง response ของ poe.ninja PoE2 exchange/current/overview
# ลีกนี้ primary = divine, มี rate exalted ต่อ 1 divine.
_SAMPLE_DIVINE = json.dumps(
    {
        "items": [
            {"id": "a1", "name": "Divine Orb"},
            {"id": "a2", "name": "Exalted Orb"},
            {"id": "a3", "name": "Mirror of Kalandra"},
            {"id": "a4", "name": "Brand New Item"},  # ยังไม่มีข้อมูลซื้อขาย
        ],
        "lines": [
            {"id": "a1", "primaryValue": 1.0},
            {"id": "a2", "primaryValue": 0.005},
            {"id": "a3", "primaryValue": 250.0},
            {"id": "a4", "primaryValue": None},
        ],
        "core": {"primary": "divine", "rates": {"exalted": 200.0, "chaos": 1.0}},
    }
)

# ลีก hardcore: primary = exalted, divine แพงเกินจึงคิดราคาเป็น exalted.
_SAMPLE_EXALTED = json.dumps(
    {
        "items": [{"id": "b1", "name": "Divine Orb"}],
        "lines": [{"id": "b1", "primaryValue": 200.0}],
        "core": {"primary": "exalted", "rates": {"divine": 0.005}},
    }
)


class TestParseResponse(unittest.TestCase):
    def test_divine_primary_prices(self):
        prices = parse_response(_SAMPLE_DIVINE)
        self.assertEqual(prices["divine orb"].divine_value, 1.0)
        self.assertEqual(prices["divine orb"].exalted_value, 200.0)

    def test_exalted_value_rounding(self):
        prices = parse_response(_SAMPLE_DIVINE)
        # 0.005 divine * 200 exalted/divine = 1.0 exalted
        self.assertEqual(prices["exalted orb"].exalted_value, 1.0)
        self.assertEqual(prices["exalted orb"].divine_value, 0.005)

    def test_high_value_item(self):
        prices = parse_response(_SAMPLE_DIVINE)
        self.assertEqual(prices["mirror of kalandra"].divine_value, 250.0)

    def test_chaos_value_from_rate(self):
        prices = parse_response(_SAMPLE_DIVINE)
        # divine orb: 1.0 divine * chaos_rate(1.0) = 1.0 chaos
        self.assertEqual(prices["divine orb"].chaos_value, 1.0)
        # mirror: 250 divine * 1.0 = 250 chaos
        self.assertEqual(prices["mirror of kalandra"].chaos_value, 250.0)

    def test_null_primary_value_marked_no_market_data(self):
        prices = parse_response(_SAMPLE_DIVINE)
        entry = prices["brand new item"]
        self.assertFalse(entry.has_market_data)
        self.assertEqual(entry.divine_value, 0.0)

    def test_exalted_primary_league(self):
        prices = parse_response(_SAMPLE_EXALTED)
        # primaryValue 200 exalted -> divine = 200 * 0.005 = 1.0
        self.assertEqual(prices["divine orb"].exalted_value, 200.0)
        self.assertEqual(prices["divine orb"].divine_value, 1.0)

    def test_keys_are_normalized(self):
        prices = parse_response(_SAMPLE_DIVINE)
        self.assertIn("mirror of kalandra", prices)
        self.assertNotIn("Mirror of Kalandra", prices)


if __name__ == "__main__":
    unittest.main()
