"""CLI demo: `python -m poe_price [league] [--search ชื่อไอเทม]`

ดึงราคาจริงจาก poe.ninja แล้วแสดงจำนวนไอเทม + ตัวอย่างที่แพงสุด,
หรือค้นราคาไอเทมตามชื่อด้วย --search.
"""

from __future__ import annotations

import argparse
import sys

from .repository import PriceRepository


def main(argv: list[str] | None = None) -> int:
    # คอนโซล Windows ดีฟอลต์เป็น cp1252 พิมพ์ไทยไม่ได้ — บังคับเป็น UTF-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(prog="poe_price", description="PoE2 price helper (poe.ninja)")
    parser.add_argument("league", nargs="?", default="Runes of Aldur", help='ชื่อลีก (ดีฟอลต์ "Runes of Aldur")')
    parser.add_argument("--search", "-s", metavar="NAME", help="ค้นราคาไอเทมตามชื่อ")
    parser.add_argument("--top", "-n", type=int, default=15, help="โชว์ N อันดับแพงสุด (ดีฟอลต์ 15)")
    args = parser.parse_args(argv)

    repo = PriceRepository(league=args.league)
    print(f"กำลังดึงราคาจาก poe.ninja (league={args.league}) ...")
    snapshot = repo.fetch()

    if snapshot.item_count == 0:
        print("ดึงราคาไม่ได้เลย — เช็คชื่อลีกหรือการเชื่อมต่ออินเทอร์เน็ต", file=sys.stderr)
        return 1

    print(f"ได้ราคา {snapshot.item_count} รายการ\n")

    if args.search:
        result = repo.match(args.search)  # fuzzy: ทนชื่อพิมพ์/อ่านเพี้ยน
        if result.is_gem and not result.matched():
            print(f'"{args.search}": เป็น uncut gem แต่อ่านชนิด/เลเวลไม่ครบ -> ?')
            return 0
        if not result.matched():
            print(f'ไม่พบ "{args.search}"')
            return 1
        entry = result.entry
        # บอกว่า match มายังไง (ถ้าไม่ใช่ชื่อตรงเป๊ะ)
        how = ""
        if result.method == "fuzzy":
            how = f'  [fuzzy -> "{result.key}" score={result.score:.2f}]'
        elif result.method == "prefix":
            how = f'  [prefix -> "{result.key}"]'
        elif result.method == "gem":
            how = f'  [gem -> "{result.key}"]'
        if not entry.has_market_data:
            print(f'"{args.search}": รู้จักไอเทม แต่ยังไม่มีข้อมูลซื้อขาย{how}')
            return 0
        print(f'"{args.search}":  {entry.divine_value:.4g} divine  ({entry.exalted_value:g} exalted){how}')
        return 0

    priced = [(k, e) for k, e in snapshot.prices.items() if e.has_market_data]
    priced.sort(key=lambda kv: kv[1].divine_value, reverse=True)
    print(f"แพงสุด {min(args.top, len(priced))} อันดับ (divine):")
    for name, entry in priced[: args.top]:
        print(f"  {entry.divine_value:>10.4g} div  {entry.exalted_value:>10g} ex   {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
