"""เทสต์ fuzzy matching — port มาจาก FuzzyMatchTests.cs ของต้นฉบับ + เคส resolve.
รันแบบ offline ล้วน."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poe_price.matcher import (
    FUZZY_THRESHOLD,
    best_fuzzy,
    levenshtein,
    resolve,
    try_resolve_gem_key,
)
from poe_price.models import PriceEntry, PriceSnapshot


def _snapshot(*names: str) -> PriceSnapshot:
    """สร้าง snapshot จากรายชื่อ key (สมมติราคา 1 divine ทุกตัว)."""
    prices = {n: PriceEntry(1.0, 100.0) for n in names}
    by_len: dict[int, list[str]] = {}
    for k in prices:
        by_len.setdefault(len(k), []).append(k)
    return PriceSnapshot(prices=prices, keys_by_length=by_len, fetched_at=0.0)


class TestLevenshtein(unittest.TestCase):
    def test_known_distances(self):
        self.assertEqual(levenshtein("", ""), 0)
        self.assertEqual(levenshtein("abc", "abc"), 0)
        self.assertEqual(levenshtein("abc", "abd"), 1)
        self.assertEqual(levenshtein("kitten", "sitting"), 3)
        self.assertEqual(levenshtein("vision", "viswn"), 2)


class TestSimilarityThreshold(unittest.TestCase):
    def _score(self, a: str, b: str) -> float:
        return 1.0 - levenshtein(a, b) / max(len(a), len(b))

    def test_absorbs_misreads_but_not_wrong_items(self):
        cases = [
            ("greater viswn rune", "greater vision rune", True),
            ("greater reblrth rune", "greater rebirth rune", True),
            ("grgater inspiration rune", "greater inspiration rune", True),
            ("greater vision rune", "greater rebirth rune", False),  # คนละไอเทม ห้าม match
        ]
        for ocr, key, should in cases:
            with self.subTest(ocr=ocr):
                self.assertEqual(self._score(ocr, key) > FUZZY_THRESHOLD, should)


class TestGemResolution(unittest.TestCase):
    def test_pins_type_and_level(self):
        cases = [
            ("uncut spirit gem level 19", "uncut spirit gem level 19"),
            ("uncut skill gem level 7", "uncut skill gem level 7"),
            ("uncut support gem level 3", "uncut support gem level 3"),
            ("uncot spirit gem level 19", "uncut spirit gem level 19"),  # boilerplate เพี้ยน
        ]
        for ocr, expected in cases:
            with self.subTest(ocr=ocr):
                is_gem, key = try_resolve_gem_key(ocr)
                self.assertTrue(is_gem)
                self.assertEqual(key, expected)

    def test_gem_without_level_recognised_but_no_key(self):
        is_gem, key = try_resolve_gem_key("uncut spirit gem")
        self.assertTrue(is_gem)
        self.assertIsNone(key)

    def test_non_gem_returns_false(self):
        for ocr in ("greater vision rune", "exalted orb"):
            with self.subTest(ocr=ocr):
                is_gem, key = try_resolve_gem_key(ocr)
                self.assertFalse(is_gem)
                self.assertIsNone(key)


class TestBestFuzzy(unittest.TestCase):
    def test_finds_near_match(self):
        snap = _snapshot("greater vision rune", "greater rebirth rune")
        found = best_fuzzy(snap.keys_by_length, "greater viswn rune")
        self.assertIsNotNone(found)
        self.assertEqual(found[0], "greater vision rune")

    def test_no_match_below_threshold(self):
        snap = _snapshot("mirror of kalandra")
        self.assertIsNone(best_fuzzy(snap.keys_by_length, "exalted orb"))


class TestResolve(unittest.TestCase):
    def test_exact(self):
        snap = _snapshot("divine orb", "exalted orb")
        r = resolve(snap, "Divine Orb")
        self.assertTrue(r.matched())
        self.assertEqual(r.method, "exact")
        self.assertTrue(r.exact)

    def test_fuzzy_rescues_misread(self):
        snap = _snapshot("greater vision rune", "greater rebirth rune")
        r = resolve(snap, "greater viswn rune")
        self.assertTrue(r.matched())
        self.assertEqual(r.method, "fuzzy")
        self.assertEqual(r.key, "greater vision rune")

    def test_prefix_match_for_long_name(self):
        snap = _snapshot("greater rune of alacrity")
        r = resolve(snap, "greater rune of alac")  # ≥10 ตัว เป็นต้นของ key
        self.assertTrue(r.matched())
        self.assertEqual(r.method, "prefix")
        self.assertEqual(r.key, "greater rune of alacrity")

    def test_gem_exact_pin(self):
        snap = _snapshot("uncut spirit gem level 19")
        r = resolve(snap, "Uncut Spirit Gem (Level 19)")
        self.assertTrue(r.matched())
        self.assertEqual(r.method, "gem")
        self.assertTrue(r.is_gem)

    def test_gem_unknown_level_does_not_fall_to_fuzzy(self):
        # มีเจมเลเวลอื่นใน snapshot แต่อ่านเลเวลไม่ได้ -> ต้องไม่เดาเป็นเลเวลข้างเคียง
        snap = _snapshot("uncut spirit gem level 19", "uncut spirit gem level 20")
        r = resolve(snap, "uncut spirit gem")
        self.assertFalse(r.matched())
        self.assertTrue(r.is_gem)
        self.assertEqual(r.method, "gem-unknown")

    def test_short_name_no_fuzzy(self):
        # ชื่อสั้น (<6) ไม่เข้า fuzzy -> miss
        snap = _snapshot("vision")
        r = resolve(snap, "visn")
        self.assertFalse(r.matched())
        self.assertEqual(r.method, "miss")

    def test_outright_miss(self):
        snap = _snapshot("divine orb")
        r = resolve(snap, "totally unknown item")
        self.assertFalse(r.matched())
        self.assertEqual(r.method, "miss")


if __name__ == "__main__":
    unittest.main()
