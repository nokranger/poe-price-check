"""เทสต์ lookup ข่าวลือ Expedition — จับชื่อจาก OCR (ทนเพี้ยน) -> map/mods/rating."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poe_price.expedition import RUMOURS, find_in_lines, lookup


class TestExpedition(unittest.TestCase):
    def test_exact_names(self):
        self.assertEqual(lookup("Sulphite!").map, "Scorched Cay")
        self.assertEqual(lookup("Fallen Stars").rating, "S+")
        self.assertEqual(lookup("Bleak and Awful").rating, "F")

    def test_ingame_flavor_text(self):
        # ชื่อที่เกมโชว์จริง (มี ... และ apostrophe) ต้องจับได้ด้วย fuzzy
        self.assertEqual(lookup("Somethin' fishy...").name, "Something Fishy")
        self.assertEqual(lookup("Wild roaming free...").name, "Wild, Roaming Free")

    def test_ingame_names_that_differ(self):
        # เคสที่เคย detect ไม่ได้ (ชื่อในเกมต่างจากชีต)
        self.assertEqual(lookup("The last to fall...").name, "Last to Fall")
        self.assertEqual(lookup("Warm but risky...").name, "It's Warm")
        self.assertEqual(lookup("Cold as ice...").map, "Frigid Bluffs")
        self.assertEqual(lookup("Sulphite!").map, "Scorched Cay")

    def test_strip_parenthetical(self):
        # ชื่อแบบในชีตที่มีวงเล็บต่อท้าย ก็ยังจับได้
        self.assertEqual(lookup("Sulphite!(Grand Expedition)").map, "Scorched Cay")

    def test_garbled_ocr_recovered_by_tokens(self):
        # ข้อความมั่วจริงจาก last_scan.txt — จับด้วย token matcher (คำเด่นพอถูก)
        self.assertEqual(lookup("A pod fellow...").name, "A Good Fellow")
        self.assertEqual(lookup("$ometWiw' fishv...").name, "Something Fishy")

    def test_unknown_ruins_ocr_alias(self):
        # minim-heavy -> OCR อ่านเป็น "Uwkwoww miws" คงที่ -> alias ดักไว้
        self.assertEqual(lookup("Uwkwoww miws...").name, "Unknown Ruins")

    def test_its_dry_at_least_ocr_alias(self):
        # OCR อ่าน "It's dry at least" ผิดเป็น "It's at lust" คงที่ทุก scale -> alias ดักไว้
        self.assertEqual(lookup("It's at lust...").name, "It's Dry at Least")
        # ต้องไม่ชน Last to Fall (lust ใกล้ last)
        self.assertEqual(lookup("The last to fall...").name, "Last to Fall")

    def test_no_match_returns_none(self):
        self.assertIsNone(lookup("Chaos Orb"))
        self.assertIsNone(lookup("Prismatic Alloy"))
        self.assertIsNone(lookup(""))

    def test_no_false_positive_on_items(self):
        # ชื่อไอเทม/ค่าเงินตอนเช็คราคา ต้องไม่ไปโผล่เป็นข่าวลือ (กัน panel เด้งมั่ว)
        for name in ("Divine Orb", "Greater Vision Rune", "Exalted Orb",
                     "Mirror of Kalandra", "Prismatic Alloy"):
            with self.subTest(name=name):
                self.assertIsNone(lookup(name))

    def test_all_rumours_self_match(self):
        # ทุก entry ต้อง lookup ตัวเองเจอ (กันพิมพ์คีย์ผิด)
        for r in RUMOURS:
            with self.subTest(name=r.name):
                self.assertEqual(lookup(r.name).name, r.name)


class TestFindInLines(unittest.TestCase):
    # บรรทัดจริงจาก last_scan.txt ในเกม
    REAL = ["POE Price", "UNCHARTED WATERS", "..USE A LOGBOOK TO CHART THE AREA",
            "ISLAND RUMOURS", "A pod fellow...", "Sovue&viw' fishv...", "It's at lust...",
            "REQUIRES:", "h: Expedition Logbook", "@Open Side Panel"]

    def test_only_matches_inside_rumour_region(self):
        names = [r.name for _, r in find_in_lines(self.REAL)]
        self.assertIn("A Good Fellow", names)
        self.assertIn("Something Fishy", names)

    def test_no_false_positive_from_window_title(self):
        # "UNCHARTED WATERS" (เหนือหัวข้อ) ต้องไม่ไปชน "Reflective Waters"
        names = [r.name for _, r in find_in_lines(self.REAL)]
        self.assertNotIn("Reflective Waters", names)

    def test_no_header_means_no_rumours(self):
        # หน้าเช็คราคาปกติ (ไม่มี "Island Rumours") ต้องคืนว่าง — กัน false positive
        self.assertEqual(find_in_lines(["Chaos Orb", "Divine Orb", "Uncharted Waters"]), [])

    def test_region_lenient_catches_garbled_warm(self):
        # ในช่วง region ผ่อนเกณฑ์ -> "warm" ที่ OCR พลาดตัวเดียวก็ยังจับได้
        lines = ["ISLAND RUMOURS", "Worm but risky...", "Wild roaming free...", "REQUIRES:"]
        names = [r.name for _, r in find_in_lines(lines)]
        self.assertIn("It's Warm", names)
        self.assertIn("Wild, Roaming Free", names)


if __name__ == "__main__":
    unittest.main()
