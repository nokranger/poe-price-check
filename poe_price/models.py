"""Data models สำหรับเก็บราคา."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PriceEntry:
    """ราคาของไอเทมหนึ่งชิ้น.

    poe.ninja ตั้งราคาในสกุล "primary" ของลีกนั้น ๆ (softcore = divine,
    hardcore = exalted) เราจึงเก็บค่าทั้งสองสกุลไว้เลย เพื่อให้ฝั่งแสดงผล
    เลือกได้ว่าจะโชว์เป็น divine หรือ exalted (เวลาค่าน้อยกว่า 1 divine).

    เก็บราคาเป็น 3 สกุล (divine/exalted/chaos) เพื่อให้ผู้ใช้เลือกหน่วยแสดงผลได้ —
    คำนวณจาก primaryValue × อัตราใน core.rates ตอน parse.

    has_market_data = False หมายถึงไอเทมนี้ poe.ninja รู้จัก แต่ยังไม่มีข้อมูล
    การซื้อขาย — overlay จะได้โชว์ว่า "ไม่มีข้อมูล" แทนที่จะมองไม่เห็นไอเทม.
    """

    divine_value: float
    exalted_value: float
    chaos_value: float = 0.0
    has_market_data: bool = True


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    """ภาพ snapshot ของราคาทั้งหมด ณ เวลาหนึ่ง.

    prices และ keys_by_length ถูกเผยแพร่พร้อมกันแบบ atomic เพื่อให้ผู้อ่าน
    (เช่น loop ของ OCR ในอนาคต) ไม่มีทางเห็น prices ใหม่คู่กับ index เก่า
    ระหว่างที่ background refresh กำลังทำงาน.

    - prices:         key (ชื่อ normalize แล้ว) -> PriceEntry
    - keys_by_length: ความยาวของ key -> รายชื่อ key ที่ยาวเท่านั้น
                      (เตรียมไว้ให้ fuzzy matcher ตอนทำ OCR ใช้ค้นเร็ว ๆ)
    - fetched_at:     epoch seconds ที่ดึงสำเร็จ (None = ยังไม่เคยดึง)
    """

    prices: dict[str, PriceEntry]
    keys_by_length: dict[int, list[str]]
    fetched_at: float | None = None

    @property
    def item_count(self) -> int:
        return len(self.prices)
