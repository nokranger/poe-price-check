"""Overlay โปร่งใส คลิกทะลุ วางทับเกม — tkinter (มากับ Python) + win32 ผ่าน ctypes.

วาดราคาแบบ: [ไอคอน currency] [ตัวเลข] บนแถบพื้นหลังทึบบาง ๆ (อ่านง่ายบนพื้นเกม).
ไอคอนโหลดจากโฟลเดอร์ img/ (divine.png / exalt.png / chaos.png).

ความปลอดภัย: overlay นี้ "วาดทับ" หน้าจอเฉย ๆ ไม่ได้ยุ่งกับหน้าต่างเกมหรือ
หน่วยความจำเกมเลย. ตั้ง WS_EX_TRANSPARENT ให้คลิกทะลุทุกจุด และ WS_EX_NOACTIVATE
ให้ไม่แย่งโฟกัสจากเกม.
"""

from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk
from ctypes import wintypes
from dataclasses import dataclass

_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020  # คลิกทะลุ (เมาส์ทุกอย่างผ่านไปหาเกม)
_WS_EX_TOOLWINDOW = 0x00000080  # ไม่โผล่ใน Alt-Tab / taskbar
_WS_EX_NOACTIVATE = 0x08000000  # ไม่แย่งโฟกัส

_TRANSPARENT_KEY = "#010101"     # สีคีย์ที่จะถูกทำให้โปร่งใส (พื้นที่ว่าง = คลิกทะลุ)
_TRANSPARENT_KEY_REF = 0x010101  # COLORREF ของสีคีย์ (0x00BBGGRR)

# ความโปร่งแสงของ"ทุกอย่างที่วาด" (พื้นหลัง+ไอคอน+ตัวเลข) 0-255; 255=ทึบสุด.
# ใช้ per-window alpha จริงของ Windows (SetLayeredWindowAttributes แบบ COLORKEY+ALPHA)
# จึงโปร่งแสงเนียน เห็นเกมทะลุได้จริง ไม่ใช่ลายจุดแบบ stipple. ปรับได้ที่นี่.
_WINDOW_ALPHA = 190

# แถบพื้นหลังราคา — สีทึบเรียบ (ความโปร่งแสงมาจาก _WINDOW_ALPHA ของทั้งหน้าต่าง)
_BG_FILL = "#000000"
_BG_PAD_X = 5
_BG_PAD_Y = 2

_FONT = ("Segoe UI", 12, "bold")
_ICON_TARGET = 22  # px ความสูงไอคอนที่ต้องการ (รูปต้นฉบับ 64px -> subsample)

# ---- panel ข่าวลือ Expedition (ตาราง Rumour | Map | Mods | Rating) ----
_PANEL_FONT = ("Segoe UI", 11)
_PANEL_HEAD_FONT = ("Segoe UI", 10, "bold")
_PANEL_BG = "#0a0a0a"
_PANEL_ROW_H = 22
_PANEL_PAD = 10
# ตำแหน่ง x ของแต่ละคอลัมน์ (อิงมุมซ้ายบนของ panel) + ความกว้างรวม
_PANEL_COLS = ((0, "Rumour"), (175, "Map"), (330, "Mods"), (510, "Rating"))
_PANEL_W = 560
# สีตามเทียร์ — ยิ่งดียิ่งสว่าง/เขียว, แย่ -> ส้ม/แดง, ไม่รู้จัก -> เทา
_RATING_COLORS = {
    "S+": "#ffd24a", "S": "#ffd24a",
    "A+": "#7BE06B", "A": "#7BE06B",
    "B+": "#5aa9ff", "B": "#5aa9ff",
    "C": "#e6c84a", "D": "#e69a4a", "F": "#e0564a",
}


def _rating_color(rating: str) -> str:
    return _RATING_COLORS.get(rating.strip(), "#9aa0a6")

_LWA_COLORKEY = 0x1
_LWA_ALPHA = 0x2

# ชื่อไอคอน -> ไฟล์ใน img/. divine/exalted/chaos = หน่วยเงินปกติ,
# mageblood/mirror = ของพิเศษ (ดู specials.py). เพิ่มไอคอนใหม่เติมที่นี่.
_ICON_FILES = {
    "divine": "divine.png",
    "exalted": "exalt.png",
    "chaos": "chaos.png",
    "mageblood": "Mageblood.png",
    "mirror": "Mirror.png",
}

_user32 = ctypes.windll.user32
_user32.GetWindowLongW.restype = wintypes.LONG
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetWindowLongW.restype = wintypes.LONG
_user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
_user32.GetParent.restype = wintypes.HWND
_user32.GetParent.argtypes = [wintypes.HWND]
_user32.SetLayeredWindowAttributes.argtypes = [
    wintypes.HWND, wintypes.COLORREF, ctypes.c_ubyte, wintypes.DWORD
]


def _img_dir() -> str:
    """โฟลเดอร์รูป — รองรับทั้งรันจากซอร์สและ freeze เป็น .exe (PyInstaller)."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
    return os.path.join(base, "img")


@dataclass(frozen=True, slots=True)
class OverlayItem:
    """ป้ายราคาหนึ่งอัน. text = ตัวเลข (เช่น "25.3" หรือ "2x 2.8" หรือ "?").
    unit = หน่วยเงิน (divine/exalted/chaos) ไว้เลือกไอคอน; None = ไม่มีไอคอน."""

    x: float
    y: float
    text: str
    unit: str | None = None
    color: str = "#ffd56b"  # เหลืองทองอ่านง่าย


class Overlay:
    def __init__(self, alpha: int = _WINDOW_ALPHA) -> None:
        self._alpha = max(20, min(255, int(alpha)))
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", _TRANSPARENT_KEY)
        self.root.configure(bg=_TRANSPARENT_KEY)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")

        self.canvas = tk.Canvas(
            self.root, width=sw, height=sh, bg=_TRANSPARENT_KEY,
            highlightthickness=0, bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.root.update_idletasks()
        self._apply_click_through()
        self._icons = self._load_icons()

    def _load_icons(self) -> dict[str, tk.PhotoImage]:
        """โหลดไอคอน currency แล้วย่อให้สูง ~_ICON_TARGET. ถ้าหาไฟล์ไม่เจอก็คืน dict ว่าง
        (render จะ fallback ไปโชว์ชื่อหน่วยเป็นตัวอักษรแทน)."""
        icons: dict[str, tk.PhotoImage] = {}
        for unit, filename in _ICON_FILES.items():
            path = os.path.join(_img_dir(), filename)
            if not os.path.exists(path):
                continue
            try:
                img = tk.PhotoImage(file=path, master=self.root)
                factor = max(1, round(img.height() / _ICON_TARGET))
                icons[unit] = img.subsample(factor, factor) if factor > 1 else img
            except tk.TclError as exc:
                print(f"[overlay] โหลดไอคอน {filename} ไม่ได้: {exc}")
        return icons

    def _hwnd(self) -> int:
        wid = self.root.winfo_id()
        parent = _user32.GetParent(wid)
        return parent or wid

    def _apply_click_through(self) -> None:
        hwnd = self._hwnd()
        style = _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        style |= _WS_EX_LAYERED | _WS_EX_TRANSPARENT | _WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE
        _user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style)
        # COLORKEY = พื้นที่ว่างโปร่งใส 100% (คลิกทะลุ), ALPHA = ของที่วาดโปร่งแสงเนียน
        _user32.SetLayeredWindowAttributes(
            hwnd, _TRANSPARENT_KEY_REF, self._alpha, _LWA_COLORKEY | _LWA_ALPHA
        )

    def set_alpha(self, alpha: int) -> None:
        """ปรับความโปร่งแสงของ overlay ตอนรันไทม์ (0-255)."""
        self._alpha = max(20, min(255, int(alpha)))
        _user32.SetLayeredWindowAttributes(
            self._hwnd(), _TRANSPARENT_KEY_REF, self._alpha, _LWA_COLORKEY | _LWA_ALPHA
        )

    def render(self, items: list[OverlayItem]) -> None:
        """ลบของเก่าแล้ววาดใหม่ทั้งหมด. เรียกจาก Tk thread เท่านั้น."""
        self.canvas.delete("all")
        for i, it in enumerate(items):
            self._draw_item(i, it)

    def _draw_item(self, index: int, it: OverlayItem) -> None:
        tag = f"it{index}"
        icon = self._icons.get(it.unit) if it.unit else None
        text_x = it.x
        if icon is not None:
            self.canvas.create_image(it.x, it.y, image=icon, anchor="w", tags=tag)
            text_x = it.x + icon.width() + 5
            label = it.text
        else:
            # ไม่มีไอคอน -> เติมชื่อหน่วยเป็นตัวอักษร (ยกเว้น "?" ที่ unit เป็น None)
            label = f"{it.text} {it.unit}" if it.unit else it.text

        # เงาดำให้ตัวเลขอ่านชัด + ตัวเลขจริง
        self.canvas.create_text(text_x + 1, it.y + 1, text=label, anchor="w",
                                fill="#000000", font=_FONT, tags=tag)
        self.canvas.create_text(text_x, it.y, text=label, anchor="w",
                                fill=it.color, font=_FONT, tags=tag)

        # แถบพื้นหลังบาง ๆ ครอบไอคอน+ตัวเลข แล้วดันไปอยู่ข้างหลัง
        bbox = self.canvas.bbox(tag)
        if bbox:
            x0, y0, x1, y1 = bbox
            bg = self.canvas.create_rectangle(
                x0 - _BG_PAD_X, y0 - _BG_PAD_Y, x1 + _BG_PAD_X, y1 + _BG_PAD_Y,
                fill=_BG_FILL, outline="", tags=f"{tag}bg",
            )
            self.canvas.tag_lower(bg, tag)

    def draw_rumour_panel(self, rumours: list, x: float, y: float) -> None:
        """วาดตารางข่าวลือ Expedition (Rumour | Map | Mods | Rating) ที่พิกัด (x,y).
        rumours = list ของ Rumour (มี .name/.map/.mods/.rating). วาดทับของเดิม
        (ไม่ล้าง canvas) — เรียกหลัง render() แล้ว. ดันให้อยู่ในจอถ้าล้นขวา/ล่าง."""
        if not rumours:
            return
        c = self.canvas
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        height = _PANEL_PAD * 2 + _PANEL_ROW_H * (len(rumours) + 1)
        # กันล้นจอ
        x = max(8, min(int(x), sw - _PANEL_W - 8))
        y = max(8, min(int(y), sh - height - 8))

        c.create_rectangle(x, y, x + _PANEL_W, y + height,
                           fill=_PANEL_BG, outline="#3a3a3a", tags="rumour")
        cx = x + _PANEL_PAD
        cy = y + _PANEL_PAD
        # หัวตาราง
        for col_x, title in _PANEL_COLS:
            c.create_text(cx + col_x, cy, text=title, anchor="nw",
                          fill="#a9a9a9", font=_PANEL_HEAD_FONT, tags="rumour")
        cy += _PANEL_ROW_H
        # แถวข้อมูล
        for r in rumours:
            cells = (r.name, r.map, r.mods)
            for (col_x, _), value in zip(_PANEL_COLS, cells):
                c.create_text(cx + col_x, cy, text=value, anchor="nw",
                              fill="#ececec", font=_PANEL_FONT, tags="rumour")
            c.create_text(cx + _PANEL_COLS[3][0], cy, text=r.rating, anchor="nw",
                          fill=_rating_color(r.rating), font=_FONT, tags="rumour")
            cy += _PANEL_ROW_H

    def clear(self) -> None:
        self.canvas.delete("all")

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass
