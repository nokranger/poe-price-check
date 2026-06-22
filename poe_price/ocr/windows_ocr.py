"""Windows OCR backend — ใช้ engine OCR ที่มากับ Windows 10/11 ผ่าน WinRT.

ข้อดีสำหรับ portable: ไม่ต้องแถมไฟล์ภาษา/ไม่ต้องลง engine แยก เพราะ OCR
ติดมากับ OS อยู่แล้ว. ต้องการแค่ winrt binding (โปรเจคชันทางการของ Microsoft)
ซึ่งตอน freeze เป็น .exe ด้วย PyInstaller จะถูกฝังเข้าไปให้เอง.

ขั้นตอน: BMP bytes -> WinRT stream -> BitmapDecoder -> SoftwareBitmap ->
OcrEngine.recognize -> แปลงผลเป็น dataclass กลาง (OcrResult).
"""

from __future__ import annotations

import asyncio

from ..capture import Capture
from .base import OcrLine, OcrResult, OcrWord


class WindowsOcrEngine:
    """OcrEngine ที่ใช้ Windows.Media.Ocr. สร้าง WinRT OcrEngine ครั้งเดียวแล้วใช้ซ้ำ."""

    def __init__(self) -> None:
        # import แบบ lazy ในตัว — ให้ ImportError ชัดเจนถ้ายังไม่ได้ลง winrt
        try:
            from winrt.windows.media.ocr import OcrEngine as _WinOcr
        except ImportError as exc:  # pragma: no cover - ขึ้นกับ env
            raise RuntimeError(
                "ยังไม่ได้ติดตั้ง winrt binding — รัน:\n"
                "  pip install winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging "
                "winrt-Windows.Storage.Streams winrt-Windows.Foundation"
            ) from exc

        self._engine = _WinOcr.try_create_from_user_profile_languages()
        if self._engine is None:
            raise RuntimeError(
                "Windows ไม่มีภาษา OCR ที่ใช้ได้ — ติดตั้ง Language pack "
                "(Settings > Time & Language > Language) แล้วลองใหม่"
            )

    def recognize(self, capture: Capture) -> OcrResult:
        return asyncio.run(self._recognize_async(capture))

    async def _recognize_async(self, capture: Capture) -> OcrResult:
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(capture.to_bmp())
        await writer.store_async()
        await writer.flush_async()
        writer.detach_stream()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await self._engine.recognize_async(bitmap)

        lines: list[OcrLine] = []
        for line in result.lines:
            words = tuple(
                OcrWord(
                    text=w.text,
                    x=w.bounding_rect.x,
                    y=w.bounding_rect.y,
                    width=w.bounding_rect.width,
                    height=w.bounding_rect.height,
                )
                for w in line.words
            )
            lines.append(OcrLine(text=line.text, words=words))
        return OcrResult(lines=tuple(lines))
