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
    """OcrEngine ที่ใช้ Windows.Media.Ocr. สร้าง WinRT OcrEngine ครั้งเดียวแล้วใช้ซ้ำ.

    scale: ขยายภาพก่อน OCR (default 2 เท่า). Windows OCR อ่านตัวอักษรใหญ่แม่นกว่ามาก
    โดยเฉพาะ font แฟนซีบนพื้น parchment ของเกม + ชื่อสั้น ๆ ที่ทนพลาดได้น้อย.
    พิกัด bbox ที่ได้จะถูกหารกลับด้วย scale ให้เป็นพิกัดจอจริง.
    """

    def __init__(self, scale: int = 2) -> None:
        # import แบบ lazy ในตัว — ให้ ImportError ชัดเจนถ้ายังไม่ได้ลง winrt
        try:
            from winrt.windows.media.ocr import OcrEngine as _WinOcr
        except ImportError as exc:  # pragma: no cover - ขึ้นกับ env
            raise RuntimeError(
                "ยังไม่ได้ติดตั้ง winrt binding — รัน:\n"
                "  pip install winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging "
                "winrt-Windows.Storage.Streams winrt-Windows.Foundation"
            ) from exc

        # 1) ลองตามภาษาใน user profile ก่อน (ปกติได้)
        self._engine = _WinOcr.try_create_from_user_profile_languages()
        # 2) บางเครื่องคืน None ทั้งที่มีภาษา OCR ติดตั้งอยู่ (ขึ้นกับ profile language)
        #    -> fallback: ใช้ภาษา OCR ที่ "มีในเครื่อง" ตัวใดก็ได้ (ราคา/ชื่อเป็นอังกฤษ ใช้ en ได้)
        if self._engine is None:
            self._engine = self._fallback_engine(_WinOcr)
        if self._engine is None:
            raise RuntimeError(
                "Windows ไม่มีภาษา OCR ที่ใช้ได้\n\n"
                "วิธีแก้ (เลือกทางใดทางหนึ่ง):\n"
                "1) PowerShell (Run as administrator) แล้วรัน:\n"
                '   Add-WindowsCapability -Online -Name "Language.OCR~~~en-US~0.0.1.0"\n'
                "2) Settings > Time & language > Language & region > English > ⋮ Language options\n"
                "   > Optional features > เพิ่ม 'Optical character recognition'\n"
                "เสร็จแล้วเปิดโปรแกรมใหม่"
            )
        self._scale = max(1, int(scale))
        self._max_dim = _WinOcr.max_image_dimension  # OCR รับภาพได้ใหญ่สุดเท่านี้ (px)

    @staticmethod
    def _fallback_engine(win_ocr):
        """ลองสร้าง engine จากภาษา OCR ที่ติดตั้งในเครื่อง (en-US/en ก่อน แล้วตัวแรกที่มี)."""
        try:
            from winrt.windows.globalization import Language

            for tag in ("en-US", "en"):
                eng = win_ocr.try_create_from_language(Language(tag))
                if eng is not None:
                    return eng
        except Exception:
            pass
        try:
            langs = win_ocr.available_recognizer_languages  # ภาษา OCR ที่ติดตั้งจริง
            if langs:
                for lang in langs:
                    eng = win_ocr.try_create_from_language(lang)
                    if eng is not None:
                        return eng
        except Exception:
            pass
        return None

    def recognize(self, capture: Capture) -> OcrResult:
        return asyncio.run(self._recognize_async(capture))

    async def _recognize_async(self, capture: Capture) -> OcrResult:
        from winrt.windows.graphics.imaging import (
            BitmapAlphaMode,
            BitmapDecoder,
            BitmapInterpolationMode,
            BitmapPixelFormat,
            BitmapTransform,
            ColorManagementMode,
            ExifOrientationMode,
        )
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(capture.to_bmp())
        await writer.store_async()
        await writer.flush_async()
        writer.detach_stream()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)

        # เลือก scale ที่ไม่ทำให้ภาพเกินขนาดสูงสุดที่ OCR รับได้
        scale = self._scale
        while scale > 1 and (capture.width * scale > self._max_dim or capture.height * scale > self._max_dim):
            scale -= 1

        if scale > 1:
            transform = BitmapTransform()
            transform.scaled_width = capture.width * scale
            transform.scaled_height = capture.height * scale
            transform.interpolation_mode = BitmapInterpolationMode.FANT  # คุณภาพสูง
            bitmap = await decoder.get_software_bitmap_transformed_async(
                BitmapPixelFormat.BGRA8, BitmapAlphaMode.PREMULTIPLIED,
                transform, ExifOrientationMode.IGNORE_EXIF_ORIENTATION,
                ColorManagementMode.DO_NOT_COLOR_MANAGE,
            )
        else:
            bitmap = await decoder.get_software_bitmap_async()

        result = await self._engine.recognize_async(bitmap)

        inv = 1.0 / scale  # หารพิกัดกลับเป็นพิกัดจอจริง
        lines: list[OcrLine] = []
        for line in result.lines:
            words = tuple(
                OcrWord(
                    text=w.text,
                    x=w.bounding_rect.x * inv,
                    y=w.bounding_rect.y * inv,
                    width=w.bounding_rect.width * inv,
                    height=w.bounding_rect.height * inv,
                )
                for w in line.words
            )
            lines.append(OcrLine(text=line.text, words=words))
        return OcrResult(lines=tuple(lines))
