"""Name normalization.

ใช้ตัวเดียวกันทั้งฝั่งที่อ่านชื่อจาก API และ (อนาคต) ฝั่งที่อ่านชื่อจาก OCR
เพื่อให้ทั้งสองทางได้ key หน้าตาเหมือนกัน แล้ว match กันเจอ.

ตรรกะตรงกับต้นฉบับ C# (NameNormalizer):
  1. ตัวพิมพ์เล็กทั้งหมด
  2. แทนทุกตัวที่ไม่ใช่ตัวอักษร/ตัวเลข/ช่องว่าง ด้วยช่องว่าง
  3. ยุบช่องว่างซ้ำให้เหลืออันเดียว แล้ว trim หัวท้าย
"""

from __future__ import annotations

import re

_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_MULTI_SPACE = re.compile(r"\s+", re.UNICODE)


def normalize(text: str) -> str:
    s = text.lower()
    s = _NON_WORD.sub(" ", s)
    s = _MULTI_SPACE.sub(" ", s)
    return s.strip()
