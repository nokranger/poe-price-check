"""หน้าต่างตั้งค่า (Settings) + หน้าวิธีใช้งาน (Help).

เป็นหน้าต่าง Tk ปกติ (มีกรอบ คลิกได้) แยกจาก overlay ที่คลิกทะลุ. เปิดด้วยปุ่ม F8.
ใช้ฟอนต์ Leelawadee UI (ไทยคมชัด) + ตัวหนา ให้อ่านง่าย.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import ttk

from .config import AppConfig
from .hotkeys import KEY_ORDER

_CURRENCIES = ["divine", "exalted", "chaos"]
_LEAGUE_SUGGESTIONS = ["Runes of Aldur", "HC Runes of Aldur", "Standard"]

# ลิงก์สนับสนุน (YouTube membership) — เปิดในเบราว์เซอร์ ไม่ล็อกฟีเจอร์ใด ๆ
SUPPORT_URL = "https://www.youtube.com/c/NokrangerChannel/join"

# ฟอนต์ที่ไทยคมชัด (มีในทุก Windows; ถ้าไม่มี Tk จะ fallback ให้เอง)
_FONT = "Leelawadee UI"
_FG = "#1a1a1a"          # สีตัวอักษรเข้ม อ่านชัด


def _fonts():
    return {
        "base": tkfont.Font(family=_FONT, size=12),
        "label": tkfont.Font(family=_FONT, size=12, weight="bold"),
        "btn": tkfont.Font(family=_FONT, size=13, weight="bold"),
        "head": tkfont.Font(family=_FONT, size=15, weight="bold"),
    }


def open_help(parent: tk.Misc) -> tk.Toplevel:
    """หน้าต่าง 'วิธีใช้งาน' — อธิบายการใช้งานเป็นภาษาไทยชัด ๆ."""
    win = tk.Toplevel(parent)
    win.title("วิธีใช้งาน — PoE Price Check")
    win.attributes("-topmost", True)
    win.resizable(False, False)
    f = _fonts()

    txt = tk.Text(win, width=50, height=28, wrap="word", font=f["base"],
                  bg="#ffffff", fg=_FG, padx=20, pady=16, relief="flat",
                  cursor="arrow", spacing2=2)
    txt.tag_configure("h", font=f["head"], foreground="#10508c", spacing1=12, spacing3=6)
    txt.tag_configure("b", font=f["label"])

    def add(text: str, tag: str | None = None):
        txt.insert("end", text + "\n", tag) if tag else txt.insert("end", text + "\n")

    add("วิธีใช้งาน 4 ขั้นตอน", "h")
    add("1. ตั้งเกมเป็นโหมด Windowed หรือ Borderless")
    add("    (ห้าม Fullscreen เด็ดขาด — ไม่งั้นจอดำ ราคาไม่ขึ้น)")
    add("2. เปิดโปรแกรม รอมุมซ้ายบนขึ้น “พร้อม! ได้ราคา…”")
    add("3. ในเกม เปิดหน้าต่างของ / ค่าเงิน / รางวัล")
    add("4. กด F9 → ราคาจะโผล่ข้างของแต่ละชิ้น (กดอีกครั้ง = ซ่อน)")

    add("ปุ่มลัด", "h")
    add("F9     แสดง / ซ่อนราคา")
    add("F6     สลับหน่วยเงิน (divine / exalted / chaos)")
    add("F8     เปิดหน้าตั้งค่า")
    add("Ctrl + Alt + Q     ปิดโปรแกรม")

    add("เคล็ดลับ", "h")
    add("•  เลื่อนหน้า/เปลี่ยนของ แล้วกด F9 ใหม่ เพื่ออ่านอีกรอบ")
    add("•  เปลี่ยนลีกได้ในช่อง League (เช่น HC Runes of Aldur)")
    add("•  ราคาอัปเดตเองทุก 30 นาที — อยากได้สดกด “ดึงราคาใหม่ตอนนี้”")

    add("ราคาไม่ขึ้น? เช็คนี่", "h")
    add("•  เกมต้องเป็น Windowed / Borderless")
    add("•  ถ้าขึ้น “ดึงราคาไม่ได้” → กด “ดึงราคาใหม่ตอนนี้”")
    add("•  ของบางชนิด (unique / เจมตัด) ยังไม่รองรับ")

    txt.configure(state="disabled")
    txt.pack(fill="both", expand=True)

    style = ttk.Style(win)
    style.configure("Help.TButton", font=f["btn"], padding=(24, 10))
    ttk.Button(win, text="ปิด (Close)", style="Help.TButton",
               command=win.destroy).pack(pady=(0, 16))

    win.transient(parent)
    win.grab_set()
    win.focus_force()
    win.update_idletasks()
    return win


def open_settings(parent: tk.Misc, config: AppConfig, on_save, on_refresh=None, on_quit=None) -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title("PoE Price Check — ตั้งค่า (Settings)")
    win.attributes("-topmost", True)
    win.resizable(False, False)
    f = _fonts()

    style = ttk.Style(win)
    style.configure(".", font=f["base"])
    style.configure("TButton", font=f["btn"], padding=(26, 12))
    style.configure("Lbl.TLabel", font=f["label"], foreground=_FG)      # ป้ายตัวหนา เข้ม
    style.configure("Dim.TLabel", font=f["base"], foreground="#777777")
    win.option_add("*TCombobox*Listbox.font", f["base"])
    win.option_add("*TCombobox*Listbox.selectBackground", "#3478f6")

    frm = ttk.Frame(win, padding=20)
    frm.grid()
    pad = {"padx": 10, "pady": 8}

    def row_label(r: int, text: str) -> None:
        ttk.Label(frm, text=text, style="Lbl.TLabel").grid(row=r, column=0, sticky="w", **pad)

    # ปุ่มวิธีใช้งาน (เด่นบนสุด — คนไม่อ่านหน้าเว็บจะได้เห็นในแอป)
    ttk.Button(frm, text="📖  วิธีใช้งานโปรแกรม (How to use)",
               command=lambda: open_help(win)).grid(row=0, column=0, columnspan=2,
                                                     sticky="ew", padx=10, pady=(0, 6))
    ttk.Separator(frm, orient="horizontal").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

    # ลีก
    row_label(2, "ลีก (League)")
    league_var = tk.StringVar(value=config.league)
    ttk.Combobox(frm, textvariable=league_var, width=24, font=f["base"],
                 values=_LEAGUE_SUGGESTIONS).grid(row=2, column=1, **pad)
    if on_refresh is not None:
        ttk.Button(frm, text="ดึงราคาใหม่ตอนนี้ (Refresh prices)",
                   command=lambda: (on_refresh(),
                                    msg.config(text="กำลังดึงราคาใหม่… (refreshing)", foreground="#2d7d2d"))
                   ).grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 4))

    # หน่วยเงิน
    row_label(4, "หน่วยเงิน (Currency)")
    currency_var = tk.StringVar(value=config.currency)
    ttk.Combobox(frm, textvariable=currency_var, width=24, state="readonly", font=f["base"],
                 values=_CURRENCIES).grid(row=4, column=1, **pad)

    # ปุ่มลัด
    toggle_var = tk.StringVar(value=config.toggle_key)
    currkey_var = tk.StringVar(value=config.currency_key)
    for r, (label, var) in enumerate([
        ("ปุ่มแสดง/ซ่อน (Show/Hide)", toggle_var),
        ("ปุ่มสลับหน่วยเงิน (Switch Currency)", currkey_var),
    ], start=5):
        row_label(r, label)
        ttk.Combobox(frm, textvariable=var, width=24, state="readonly", font=f["base"],
                     values=KEY_ORDER).grid(row=r, column=1, **pad)

    # ความทึบ
    row_label(7, "ความทึบ (Opacity)")
    alpha_var = tk.IntVar(value=config.window_alpha)
    ttk.Scale(frm, from_=60, to=255, variable=alpha_var, orient="horizontal",
              length=210).grid(row=7, column=1, **pad)

    msg = ttk.Label(frm, text="", style="Lbl.TLabel", foreground="#c0392b")
    msg.grid(row=8, column=0, columnspan=2, sticky="w", padx=10)

    def save() -> None:
        if "F8" in (toggle_var.get(), currkey_var.get()):
            msg.config(text="F8 สงวนไว้สำหรับเปิดหน้านี้ — เลือกปุ่มอื่น  (F8 is reserved)",
                       foreground="#c0392b")
            return
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

    btns = ttk.Frame(frm)
    btns.grid(row=9, column=0, columnspan=2, pady=(18, 0))
    ttk.Button(btns, text="บันทึก (Save)", command=save).grid(row=0, column=0, padx=10)
    ttk.Button(btns, text="ยกเลิก (Cancel)", command=win.destroy).grid(row=0, column=1, padx=10)

    if on_quit is not None:
        ttk.Separator(frm, orient="horizontal").grid(row=10, column=0, columnspan=2, sticky="ew", pady=(16, 6))

        def quit_app() -> None:
            win.destroy()
            on_quit()

        ttk.Button(frm, text="⨯  ปิดโปรแกรม (Quit)", command=quit_app).grid(row=11, column=0, columnspan=2, pady=(2, 0))
        ttk.Label(frm, text="(หรือกด Ctrl+Alt+Q ได้ทุกเมื่อ)", style="Dim.TLabel").grid(
            row=12, column=0, columnspan=2)

    ttk.Separator(frm, orient="horizontal").grid(row=13, column=0, columnspan=2, sticky="ew", pady=(14, 8))
    support = ttk.Label(frm, text="❤  สนับสนุนผู้พัฒนา — สมัครสมาชิกช่อง Nokranger (YouTube)",
                        foreground="#cc0000", cursor="hand2", style="Lbl.TLabel")
    support.grid(row=14, column=0, columnspan=2)
    support.bind("<Button-1>", lambda _e: webbrowser.open(SUPPORT_URL))

    ttk.Label(frm, text="ข้อมูลราคาจาก poe.ninja", style="Dim.TLabel").grid(
        row=15, column=0, columnspan=2, pady=(6, 0))

    win.transient(parent)
    win.grab_set()
    win.focus_force()
    win.update_idletasks()
    return win
