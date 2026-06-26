"""เทสต์ของพิเศษ/มุกปั่น ๆ (specials) — จับชื่อกว้าง ๆ ให้เป็นไอคอนเฉพาะ."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poe_price.specials import match_special


class TestSpecials(unittest.TestCase):
    def test_random_currency_to_mirror(self):
        s = match_special("5x Random Currency")
        self.assertIsNotNone(s)
        self.assertEqual(s.icon, "mirror")

    def test_unique_variants_to_mageblood(self):
        for name in ("Rare Unique Item", "Unique Belt", "Unique Jewellery", "Unique Jewelry"):
            with self.subTest(name=name):
                s = match_special(name)
                self.assertIsNotNone(s)
                self.assertEqual(s.icon, "mageblood")

    def test_substring_and_ocr_noise(self):
        # เจอเป็น substring กลางบรรทัด + มีอักขระแปลกจาก OCR ก็ยังจับได้
        self.assertIsNotNone(match_special(">> 5x  Random-Currency <<"))

    def test_normal_item_is_none(self):
        self.assertIsNone(match_special("Chaos Orb"))
        self.assertIsNone(match_special("Prismatic Alloy"))


if __name__ == "__main__":
    unittest.main()
