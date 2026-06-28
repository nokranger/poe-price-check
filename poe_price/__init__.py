"""poe_price — PoE2 price helper core.

ดึงราคา currency / uncut gems จาก poe.ninja (PoE2) มาเก็บไว้ในหน่วยความจำ
พร้อม cache + auto-refresh ทุก 30 นาที. ออกแบบให้เป็น data core ที่ทดสอบแยกได้
โดยไม่ผูกกับ GUI/overlay (จะมาต่อยอดทีหลัง).

ไม่มี dependency ภายนอก — ใช้ standard library ของ Python ล้วน.
"""

from .matcher import MatchResult, resolve
from .models import PriceEntry, PriceSnapshot
from .normalizer import normalize
from .repository import PriceRepository

__all__ = [
    "PriceEntry",
    "PriceSnapshot",
    "PriceRepository",
    "MatchResult",
    "resolve",
    "normalize",
]
__version__ = "0.1.6"
