"""ของพิเศษ / มุกปั่น ๆ (special overrides) — ชื่อไอเทมกว้าง ๆ ที่อยากให้โชว์
ไอคอนเฉพาะแทนราคาจริง.

ตัวอย่างที่ตั้งไว้:
  - "5x Random Currency"  -> ไอคอน Mirror (กระจก) + "5x"   (ของแรร์สุด ๆ แบบปั่น ๆ)
  - "Rare Unique Item" / "Unique Belt" / "Unique Jewellery" -> ไอคอน Mageblood

เหตุที่แยกเป็นโมดูลเดี่ยว: อยากเพิ่ม/แก้ง่าย ๆ ในแพตช์ถัด ๆ ไป — แค่เติม entry ใน
_SPECIALS ก็พอ. จับด้วย "คำสำคัญ" ที่ normalize แล้ว (ทน OCR เพี้ยน) แบบ substring
จึงไม่ต้องเป๊ะทั้งบรรทัด.

วิธีเพิ่มไอเทมพิเศษใหม่:
  1. วางไฟล์รูป (เช่น chaos.png) ไว้ในโฟลเดอร์ img/
  2. เพิ่ม mapping ชื่อไอคอน -> ไฟล์ ใน overlay._load_icons (_ICON_FILES)
  3. เพิ่ม (คำสำคัญ, Special(...)) ด้านล่าง — เรียงตัวที่เจาะจงกว่าไว้บน
"""

from __future__ import annotations

from dataclasses import dataclass

from .normalizer import normalize


@dataclass(frozen=True, slots=True)
class Special:
    icon: str                 # ชื่อไอคอนใน overlay (ต้องมีใน overlay._ICON_FILES)
    text: str                 # ข้อความที่โชว์ข้างไอคอน (เช่น "5x", "Mageblood")
    color: str = "#ffd56b"    # สีตัวอักษร


# (คำสำคัญที่ normalize แล้ว, Special) — เจอเป็น substring ในบรรทัด OCR ก็ถือว่าตรง.
# เรียงจาก "เจาะจงกว่า" ไป "กว้างกว่า" เพราะ match_special คืนตัวแรกที่เจอ.
_SPECIALS: tuple[tuple[str, Special], ...] = (
    ("random currency", Special(icon="mirror", text="5x", color="#7fe3ff")),
    ("rare unique item", Special(icon="mageblood", text="Mageblood", color="#ff9d5c")),
    ("unique belt", Special(icon="mageblood", text="Mageblood", color="#ff9d5c")),
    ("unique jewellery", Special(icon="mageblood", text="Mageblood", color="#ff9d5c")),
    ("unique jewelry", Special(icon="mageblood", text="Mageblood", color="#ff9d5c")),
)


def match_special(raw_text: str) -> Special | None:
    """คืน Special ถ้าบรรทัดนี้ตรงกับของพิเศษ; ไม่ตรง = None.
    จับด้วย substring บนข้อความที่ normalize แล้ว จึงทน OCR เพี้ยนเล็กน้อยได้."""
    norm = normalize(raw_text)
    for needle, special in _SPECIALS:
        if needle in norm:
            return special
    return None
