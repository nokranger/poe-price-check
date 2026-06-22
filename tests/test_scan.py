"""เทสต์ scan logic แบบ offline — ใช้ fake OCR + repo ที่ยัดราคาเอง ไม่แตะหน้าจอ/เน็ต."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poe_price.models import PriceEntry, PriceSnapshot
from poe_price.ocr.base import OcrLine, OcrResult, OcrWord
from poe_price.repository import PriceRepository
from poe_price.scan import parse_quantity, scan_lines


def _line(text: str, x: float = 0, y: float = 0) -> OcrLine:
    # บรรทัดที่มีคำเดียวครอบทั้งข้อความ (พอสำหรับเทสต์ bbox/center_y)
    return OcrLine(text=text, words=(OcrWord(text, x, y, 100.0, 20.0),))


def _repo(*names: str) -> PriceRepository:
    prices = {n: PriceEntry(2.0, 200.0) for n in names}
    by_len: dict[int, list[str]] = {}
    for k in prices:
        by_len.setdefault(len(k), []).append(k)
    repo = PriceRepository(league="Test")
    repo._snapshot = PriceSnapshot(prices=prices, keys_by_length=by_len, fetched_at=0.0)
    return repo


class TestParseQuantity(unittest.TestCase):
    def test_no_quantity(self):
        self.assertEqual(parse_quantity("Chaos Orb"), (1, "Chaos Orb"))

    def test_leading_nx(self):
        self.assertEqual(parse_quantity("5x Chaos Orb"), (5, "Chaos Orb"))
        self.assertEqual(parse_quantity("12X Divine Orb"), (12, "Divine Orb"))

    def test_leading_number_space(self):
        self.assertEqual(parse_quantity("3 Greater Vision Rune"), (3, "Greater Vision Rune"))

    def test_does_not_eat_level_numbers(self):
        # "level 20" ไม่ใช่จำนวนนำหน้า (ไม่ได้ขึ้นต้นด้วยเลข)
        self.assertEqual(parse_quantity("Uncut Skill Gem Level 20"), (1, "Uncut Skill Gem Level 20"))


class TestScanLines(unittest.TestCase):
    def test_matches_and_totals(self):
        repo = _repo("divine orb", "chaos orb")
        ocr = OcrResult(lines=(_line("Divine Orb", y=10), _line("5x Chaos Orb", y=30)))
        rows = scan_lines(repo, ocr)
        self.assertEqual(len(rows), 2)

        divine = next(r for r in rows if r.result.key == "divine orb")
        self.assertEqual(divine.quantity, 1)
        self.assertEqual(divine.total_divine, 2.0)

        chaos = next(r for r in rows if r.result.key == "chaos orb")
        self.assertEqual(chaos.quantity, 5)
        self.assertEqual(chaos.total_divine, 10.0)  # 2.0 * 5

    def test_unmatched_line(self):
        repo = _repo("divine orb")
        rows = scan_lines(repo, OcrResult(lines=(_line("some random label"),)))
        self.assertFalse(rows[0].matched)
        self.assertEqual(rows[0].total_divine, 0.0)

    def test_fuzzy_line_from_ocr_noise(self):
        repo = _repo("greater vision rune")
        rows = scan_lines(repo, OcrResult(lines=(_line("greater viswn rune"),)))
        self.assertTrue(rows[0].matched)
        self.assertEqual(rows[0].result.key, "greater vision rune")
        self.assertEqual(rows[0].result.method, "fuzzy")


if __name__ == "__main__":
    unittest.main()
