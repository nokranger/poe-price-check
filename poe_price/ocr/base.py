"""โครงข้อมูลผลลัพธ์ OCR + protocol ของ engine (ไม่ผูกกับ backend)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..capture import Capture


@dataclass(frozen=True, slots=True)
class OcrWord:
    """คำหนึ่งคำ พร้อมกรอบตำแหน่ง (พิกัดอิงมุมซ้ายบนของภาพที่จับ, หน่วยพิกเซล)."""

    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class OcrLine:
    """ข้อความหนึ่งบรรทัด = ลำดับของคำ. bbox คำนวณจากกรอบของทุกคำรวมกัน."""

    text: str
    words: tuple[OcrWord, ...]

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """กรอบครอบทั้งบรรทัด (x, y, width, height). ถ้าไม่มีคำ คืน (0,0,0,0)."""
        if not self.words:
            return (0.0, 0.0, 0.0, 0.0)
        left = min(w.x for w in self.words)
        top = min(w.y for w in self.words)
        right = max(w.x + w.width for w in self.words)
        bottom = max(w.y + w.height for w in self.words)
        return (left, top, right - left, bottom - top)

    @property
    def center_y(self) -> float:
        x, y, _, h = self.bbox
        return y + h / 2


@dataclass(frozen=True, slots=True)
class OcrResult:
    lines: tuple[OcrLine, ...]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@runtime_checkable
class OcrEngine(Protocol):
    """อะไรก็ตามที่ถอดข้อความจาก Capture ได้ ถือเป็น OcrEngine."""

    def recognize(self, capture: Capture) -> OcrResult: ...
