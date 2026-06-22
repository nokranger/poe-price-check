"""จับภาพหน้าจอ (บางส่วนหรือทั้งจอ) ด้วย ctypes ล้วน — ไม่มี dependency.

เรียก GDI ของ Windows ตรง ๆ (BitBlt + GetDIBits) ได้ pixel แบบ BGRA 32-bit
แล้วห่อเป็นไฟล์ BMP ในหน่วยความจำ เพื่อส่งต่อให้ OCR engine ถอดข้อความ.
"""

from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from dataclasses import dataclass

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32

_SRCCOPY = 0x00CC0020
_DIB_RGB_COLORS = 0
_BI_RGB = 0


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


# argtypes ที่ถูกต้องสำคัญมากบน 64-bit (handle เป็น pointer ไม่ใช่ int 32-bit)
_gdi32.CreateCompatibleDC.restype = wintypes.HDC
_gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
_gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
_gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
_gdi32.SelectObject.restype = wintypes.HGDIOBJ
_gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_gdi32.BitBlt.argtypes = [
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
]
_gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, ctypes.c_uint, ctypes.c_uint,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
]
_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.DeleteDC.argtypes = [wintypes.HDC]
_user32.GetDC.restype = wintypes.HDC
_user32.GetDC.argtypes = [wintypes.HWND]
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.GetSystemMetrics.argtypes = [ctypes.c_int]


def set_dpi_aware() -> None:
    """บอก Windows ว่าโปรแกรมรู้เรื่อง DPI เอง เพื่อให้พิกัด/ขนาดที่จับ ตรงกับ
    pixel จริงบนจอ scale สูง (ไม่งั้นภาพจะถูก OS ย่อ/ขยายให้เพี้ยน)."""
    try:
        # PER_MONITOR_AWARE_V2 = -4 (Windows 10 1703+)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def screen_size() -> tuple[int, int]:
    """ขนาดจอหลัก (พิกเซลจริงหลังตั้ง DPI aware แล้ว)."""
    return _user32.GetSystemMetrics(0), _user32.GetSystemMetrics(1)


@dataclass(frozen=True, slots=True)
class Capture:
    """ภาพที่จับได้: pixel BGRA ดิบ + ขนาด."""

    pixels: bytes  # BGRA top-down, len == width*height*4
    width: int
    height: int

    def to_bmp(self) -> bytes:
        """ห่อเป็นไฟล์ BMP (top-down 32bpp) สำหรับป้อน OCR decoder."""
        offset = 14 + 40  # file header + info header
        info = struct.pack(
            "<IiiHHIIiiII",
            40, self.width, -self.height, 1, 32, _BI_RGB,
            len(self.pixels), 0, 0, 0, 0,
        )
        file_header = struct.pack("<2sIHHI", b"BM", offset + len(self.pixels), 0, 0, offset)
        return file_header + info + self.pixels


def capture_region(left: int, top: int, width: int, height: int) -> Capture:
    """จับภาพสี่เหลี่ยม (left, top, width, height) จากเดสก์ท็อป."""
    if width <= 0 or height <= 0:
        raise ValueError(f"ขนาดจับภาพไม่ถูกต้อง: {width}x{height}")

    screen_dc = _user32.GetDC(None)
    mem_dc = _gdi32.CreateCompatibleDC(screen_dc)
    bitmap = _gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old = _gdi32.SelectObject(mem_dc, bitmap)
    try:
        _gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, left, top, _SRCCOPY)

        info = _BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # ลบ = top-down เรียง pixel เหมือนภาพปกติ
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = _BI_RGB

        buf = (ctypes.c_char * (width * height * 4))()
        scanned = _gdi32.GetDIBits(
            mem_dc, bitmap, 0, height, buf, ctypes.byref(info), _DIB_RGB_COLORS
        )
        if scanned == 0:
            raise OSError("GetDIBits ล้มเหลว (จับภาพหน้าจอไม่ได้)")
        return Capture(bytes(buf), width, height)
    finally:
        _gdi32.SelectObject(mem_dc, old)
        _gdi32.DeleteObject(bitmap)
        _gdi32.DeleteDC(mem_dc)
        _user32.ReleaseDC(None, screen_dc)


def capture_screen() -> Capture:
    """จับภาพทั้งจอหลัก."""
    w, h = screen_size()
    return capture_region(0, 0, w, h)
