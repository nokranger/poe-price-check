"""เทสต์ normalize — รันแบบ offline ล้วน."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poe_price.normalizer import normalize


class TestNormalize(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(normalize("Divine Orb"), "divine orb")

    def test_strips_punctuation(self):
        self.assertEqual(normalize("Chaos Orb!!!"), "chaos orb")
        self.assertEqual(normalize("Maven's Orb"), "maven s orb")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize("  Exalted    Orb  "), "exalted orb")
        self.assertEqual(normalize("Orb\tof\nAlchemy"), "orb of alchemy")

    def test_api_and_ocr_paths_agree(self):
        # ชื่อเดียวกันที่เขียนต่างกันเล็กน้อย ต้องได้ key เดียวกัน
        self.assertEqual(normalize("Uncut Skill Gem (Level 1)"), normalize("uncut skill gem level 1"))

    def test_empty(self):
        self.assertEqual(normalize("   "), "")
        self.assertEqual(normalize("!!!"), "")


if __name__ == "__main__":
    unittest.main()
