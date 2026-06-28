"""OCR subpackage — อ่านข้อความจากภาพที่จับได้.

ออกแบบเป็น pluggable: โค้ดส่วนอื่นพึ่งแค่ protocol `OcrEngine` กับ dataclass ผลลัพธ์
(`OcrResult`/`OcrLine`/`OcrWord`) ไม่ผูกกับ engine ตัวใดตัวหนึ่ง — อยากสลับจาก
Windows OCR ไป Tesseract หรืออื่น ๆ ก็แค่เขียน backend ใหม่ที่ทำตาม protocol.
"""

from __future__ import annotations

from .base import OcrEngine, OcrLine, OcrResult, OcrWord

__all__ = ["OcrEngine", "OcrResult", "OcrLine", "OcrWord", "create_default_engine"]


def create_default_engine() -> OcrEngine:
    """สร้าง engine เริ่มต้น (Windows OCR ในตัว Windows). โหลดแบบ lazy เพื่อ
    ไม่ดึง winrt มาตอน import ส่วนที่ไม่เกี่ยวกับ OCR (เช่น price core).

    scale=3: ขยายภาพ 3 เท่าก่อน OCR — ช่วยให้อ่านฟอนต์ลายมือของ Island Rumours
    (เช่น "It's dry at least...") แม่นขึ้น. จอ 4K จะถูกลดเหลือ 2x อัตโนมัติถ้าเกิน
    ขนาดสูงสุดที่ OCR รับได้ (กันภาพใหญ่เกิน)."""
    from .windows_ocr import WindowsOcrEngine

    return WindowsOcrEngine(scale=3)
