"""หน้าต่างตั้งค่า (Settings) — เลือกลีก / หน่วยเงิน / ปุ่มลัด / ความทึบ.

เป็นหน้าต่าง Tk ปกติ (มีกรอบ คลิกได้) แยกจาก overlay ที่คลิกทะลุ. เปิดด้วยปุ่ม F8.
กดบันทึกแล้วเรียก callback on_save(dict) ให้ App ไปปรับใช้ + เซฟลง config.
ข้อความสองภาษา (ไทย/อังกฤษ) ตัวอักษรใหญ่อ่านง่าย.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import ttk

from .config import AppConfig
from .hotkeys import KEY_ORDER

_CURRENCIES = ["divine", "exalted", "chaos"]
_LEAGUE_SUGGESTIONS = ["Runes of Aldur", "Standard"]

# ลิงก์สนับสนุน (YouTube membership) — เปิดในเบราว์เซอร์ ไม่ล็อกฟีเจอร์ใด ๆ
SUPPORT_URL = "https://www.youtube.com/c/NokrangerChannel/join"

_BASE_PT = 12   # ขนาดตัวอักษรหลัก
_BTN_PT = 13    # ขนาดตัวอักษรปุ่ม


def open_settings(parent: tk.Misc, config: AppConfig, on_save, on_refresh=None, on_quit=None) -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title("PoE Price Check — ตั้งค่า (Settings)")
    win.attributes("-topmost", True)
    win.resizable(False, False)

    base = tkfont.Font(family="Segoe UI", size=_BASE_PT)
    btn_font = tkfont.Font(family="Segoe UI", size=_BTN_PT, weight="bold")

    style = ttk.Style(win)
    style.configure(".", font=base)                       # ทุก ttk widget ใช้ฟอนต์นี้
    style.configure("TButton", font=btn_font, padding=(26, 12))
    style.configure("Big.TLabel", font=base)
    win.option_add("*TCombobox*Listbox.font", base)       # ฟอนต์ใน dropdown
    win.option_add("*TCombobox*Listbox.selectBackground", "#3478f6")

    frm = ttk.Frame(win, padding=20)
    frm.grid()
    pad = {"padx": 10, "pady": 8}

    def row_label(r: int, text: str) -> None:
        ttk.Label(frm, text=text, style="Big.TLabel").grid(row=r, column=0, sticky="w", **pad)

    # ลีก
    row_label(0, "ลีก (League)")
    league_frame = ttk.Frame(frm)
    league_frame.grid(row=0, column=1, sticky="w", **pad)
    league_var = tk.StringVar(value=config.league)
    ttk.Combobox(league_frame, textvariable=league_var, width=22, font=base,
                 values=_LEAGUE_SUGGESTIONS).grid(row=0, column=0)
    # ปุ่มดึงราคาใหม่ทันที (ไม่ต้องรอรอบ 30 นาที)
    if on_refresh is not None:
        ttk.Button(frm, text="ดึงราคาใหม่ตอนนี้ (Refresh prices)",
                   command=lambda: (on_refresh(),
                                    msg.config(text="กำลังดึงราคาใหม่… (refreshing)", foreground="#2d7d2d"))
                   ).grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 4))

    # หน่วยเงิน
    row_label(2, "หน่วยเงิน (Currency)")
    currency_var = tk.StringVar(value=config.currency)
    ttk.Combobox(frm, textvariable=currency_var, width=24, state="readonly", font=base,
                 values=_CURRENCIES).grid(row=2, column=1, **pad)

    # ปุ่มลัด
    toggle_var = tk.StringVar(value=config.toggle_key)
    currkey_var = tk.StringVar(value=config.currency_key)
    for r, (label, var) in enumerate([
        ("ปุ่มแสดง/ซ่อน (Show/Hide)", toggle_var),
        ("ปุ่มสลับหน่วยเงิน (Switch Currency)", currkey_var),
    ], start=3):
        row_label(r, label)
        ttk.Combobox(frm, textvariable=var, width=24, state="readonly", font=base,
                     values=KEY_ORDER).grid(row=r, column=1, **pad)

    # ความทึบ
    row_label(5, "ความทึบ (Opacity)")
    alpha_var = tk.IntVar(value=config.window_alpha)
    ttk.Scale(frm, from_=60, to=255, variable=alpha_var, orient="horizontal",
              length=210).grid(row=5, column=1, **pad)

    msg = ttk.Label(frm, text="", style="Big.TLabel", foreground="#c0392b")
    msg.grid(row=6, column=0, columnspan=2, sticky="w", padx=10)

    def save() -> None:
        if toggle_var.get() == currkey_var.get():
            msg.config(text="ปุ่มลัดซ้ำกัน — เลือกไม่ให้ซ้ำ  (duplicate keys)", foreground="#c0392b")
            return
        result = {
            "league": league_var.get().strip() or config.league,
            "currency": currency_var.get(),
            "toggle_key": toggle_var.get(),
            "currency_key": currkey_var.get(),
            "window_alpha": int(alpha_var.get()),
        }
        win.destroy()
        on_save(result)

    # บันทึก/ยกเลิก = ปิดเฉพาะหน้านี้
    btns = ttk.Frame(frm)
    btns.grid(row=7, column=0, columnspan=2, pady=(18, 0))
    ttk.Button(btns, text="บันทึก (Save)", command=save).grid(row=0, column=0, padx=10)
    ttk.Button(btns, text="ยกเลิก (Cancel)", command=win.destroy).grid(row=0, column=1, padx=10)

    # ปุ่มปิดโปรแกรม (เผื่อคนไม่รู้ปุ่มลัด Ctrl+Alt+Q) — แยกชัด ไม่ให้สับสนกับ Cancel
    if on_quit is not None:
        ttk.Separator(frm, orient="horizontal").grid(row=8, column=0, columnspan=2, sticky="ew", pady=(16, 6))

        def quit_app() -> None:
            win.destroy()
            on_quit()

        ttk.Button(frm, text="⨯  ปิดโปรแกรม (Quit)", command=quit_app).grid(
            row=9, column=0, columnspan=2, pady=(2, 0))
        ttk.Label(frm, text="(หรือกด Ctrl+Alt+Q ได้ทุกเมื่อ)", style="Big.TLabel",
                  foreground="#888888").grid(row=10, column=0, columnspan=2)

    # ปุ่มสนับสนุน (เนียน ๆ ด้านล่างสุด) — เปิด YouTube membership ในเบราว์เซอร์
    ttk.Separator(frm, orient="horizontal").grid(row=11, column=0, columnspan=2, sticky="ew", pady=(14, 8))
    support = ttk.Label(frm, text="❤  สนับสนุนผู้พัฒนา — สมัครสมาชิกช่อง Nokranger (YouTube)",
                        foreground="#cc0000", cursor="hand2", style="Big.TLabel")
    support.grid(row=12, column=0, columnspan=2)
    support.bind("<Button-1>", lambda _e: webbrowser.open(SUPPORT_URL))

    # เครดิตแหล่งข้อมูลราคา (มารยาทต่อ poe.ninja)
    ttk.Label(frm, text="ข้อมูลราคาจาก poe.ninja", style="Big.TLabel",
              foreground="#888888").grid(row=13, column=0, columnspan=2, pady=(6, 0))

    win.transient(parent)
    win.grab_set()
    win.focus_force()
    win.update_idletasks()
    return win
