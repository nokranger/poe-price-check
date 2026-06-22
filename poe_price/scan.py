"""Scan: จับภาพ -> OCR -> จับคู่ราคา. รวมทุกชิ้นเข้าด้วยกันเป็นฟีเจอร์เดียว.

แยกเป็น 2 ชั้น:
  - scan_lines(repo, ocr_result)  ฟังก์ชันบริสุทธิ์ (ทดสอบได้ด้วย fake OCR)
  - scan_region(...)              ห่อ capture + engine จริง

CLI:  python -m poe_price.scan [league] [--region L T W H]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

from .matcher import MatchResult
from .ocr.base import OcrEngine, OcrLine, OcrResult
from .repository import PriceRepository

# จำนวนนำหน้าชื่อ เช่น "5x Chaos Orb" / "3 Greater Vision Rune" -> แยกออกเป็น multiplier
_QUANTITY = re.compile(r"^\s*(\d+)\s*[x×]?\s+(?=\D)", re.IGNORECASE)


def parse_quantity(text: str) -> tuple[int, str]:
    """แยกจำนวนนำหน้าออกจากชื่อ. คืน (จำนวน, ชื่อที่เหลือ). ไม่มีจำนวน = 1."""
    m = _QUANTITY.match(text)
    if m:
        return int(m.group(1)), text[m.end():].strip()
    return 1, text.strip()


@dataclass(frozen=True, slots=True)
class ScanRow:
    """ผลของ OCR หนึ่งบรรทัด หลังจับคู่ราคาแล้ว."""

    line: OcrLine
    quantity: int
    result: MatchResult

    @property
    def matched(self) -> bool:
        return self.result.matched()

    @property
    def total_divine(self) -> float:
        return self.result.entry.divine_value * self.quantity if self.matched else 0.0

    @property
    def total_exalted(self) -> float:
        return self.result.entry.exalted_value * self.quantity if self.matched else 0.0

    @property
    def total_chaos(self) -> float:
        return self.result.entry.chaos_value * self.quantity if self.matched else 0.0

    def total(self, unit: str) -> float:
        """มูลค่ารวมตามหน่วยที่เลือก: 'divine' | 'exalted' | 'chaos'."""
        if unit == "exalted":
            return self.total_exalted
        if unit == "chaos":
            return self.total_chaos
        return self.total_divine


def scan_lines(repo: PriceRepository, ocr: OcrResult) -> list[ScanRow]:
    """จับคู่ทุกบรรทัด OCR เข้ากับราคา (ฟังก์ชันบริสุทธิ์ — ไม่แตะหน้าจอ)."""
    rows: list[ScanRow] = []
    for line in ocr.lines:
        qty, name = parse_quantity(line.text)
        rows.append(ScanRow(line=line, quantity=qty, result=repo.match(name)))
    return rows


def scan_region(
    repo: PriceRepository,
    engine: OcrEngine,
    region: tuple[int, int, int, int] | None = None,
) -> list[ScanRow]:
    """จับภาพ (region = (left, top, width, height) หรือ None = ทั้งจอ) -> OCR -> จับคู่ราคา."""
    from .capture import capture_region, capture_screen, set_dpi_aware

    set_dpi_aware()
    cap = capture_screen() if region is None else capture_region(*region)
    return scan_lines(repo, engine.recognize(cap))


def _main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(prog="poe_price.scan", description="จับภาพหน้าจอ -> อ่านราคา PoE2")
    parser.add_argument("league", nargs="?", default="Runes of Aldur")
    parser.add_argument("--region", "-r", nargs=4, type=int, metavar=("L", "T", "W", "H"),
                        help="พื้นที่ที่จะจับ (ซ้าย บน กว้าง สูง). ไม่ใส่ = ทั้งจอ")
    parser.add_argument("--all", action="store_true", help="โชว์ทุกบรรทัดรวมที่จับคู่ไม่ได้")
    args = parser.parse_args(argv)

    print(f"ดึงราคา (league={args.league}) ...")
    repo = PriceRepository(league=args.league)
    if repo.fetch().item_count == 0:
        print("ดึงราคาไม่ได้ — เช็คชื่อลีก/อินเทอร์เน็ต", file=sys.stderr)
        return 1

    print("สร้าง OCR engine + จับภาพ ...")
    from .ocr import create_default_engine

    region = tuple(args.region) if args.region else None
    rows = scan_region(repo, create_default_engine(), region)

    shown = [r for r in rows if r.matched or args.all]
    if not shown:
        print("ไม่พบไอเทมที่มีราคาในภาพ (ลองเปิดหน้าต่าง currency/รางวัลในเกมก่อน)")
        return 0

    total_div = 0.0
    for r in sorted(shown, key=lambda r: r.line.center_y):
        x, y, _, _ = r.line.bbox
        if r.matched:
            e = r.result.entry
            qty = f"{r.quantity}x " if r.quantity > 1 else ""
            tag = "" if r.result.method == "exact" else f" [{r.result.method}]"
            if e.has_market_data:
                total_div += r.total_divine
                print(f"  @({int(x):>4},{int(y):>4})  {r.total_divine:>9.4g} div  "
                      f"{qty}{r.result.key}{tag}")
            else:
                print(f"  @({int(x):>4},{int(y):>4})  {'?':>9}      {qty}{r.result.key} (ไม่มีข้อมูลซื้อขาย)")
        else:
            mark = "?" if r.result.is_gem else "-"
            print(f"  @({int(x):>4},{int(y):>4})  {mark:>9}      {r.line.text!r}")

    print(f"\nรวมที่ตีราคาได้: {total_div:.4g} divine")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
