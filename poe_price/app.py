"""ตัวโปรแกรมหลัก — overlay เช็คราคา PoE2 แบบครบวงจร.

ผูกทุกชิ้นเข้าด้วยกัน:
  - PriceRepository  : ดึง/รีเฟรชราคาเบื้องหลัง
  - HotkeyListener   : F5 toggle แสดง/ซ่อนราคา, F4 ล็อกพื้นที่, F6 สลับหน่วยเงิน, Ctrl+Alt+Q ออก
  - one-shot scan    : กด F5 = จับภาพ -> OCR -> จับคู่ราคา "ครั้งเดียว" แล้วค้างไว้ (ไม่วน = ไม่กะพริบ)
  - Overlay (Tk)     : วาดราคาข้างขวาของแต่ละชิ้น

threading: Tk อยู่ main thread เท่านั้น. hotkey/worker thread สื่อสารกลับ Tk
ผ่าน queue ที่ Tk คอยอ่านด้วย root.after — กัน race และไม่แตะ Tk ข้าม thread.

ความปลอดภัย: โปรแกรมแค่จับ "ภาพหน้าจอ" + คุยกับ poe.ninja ผ่าน HTTPS เท่านั้น
ไม่อ่าน/เขียนหน่วยความจำเกม ไม่ยิงคีย์/คลิกเข้าเกม ไม่ดักแพ็กเก็ต. ดู SECURITY.md
"""

from __future__ import annotations

import queue
import threading
import time

from .config import AppConfig
from .hotkeys import MOD_ALT, MOD_CONTROL, HotkeyListener, key_name_to_vk
from .overlay import Overlay, OverlayItem

# id ปุ่มลัด
_HK_TOGGLE = 1
_HK_QUIT = 3
_HK_CURRENCY = 4
_HK_SETTINGS = 5
_VK_Q = 0x51
_VK_F8 = 0x77  # เปิดหน้า Settings (ปุ่มตายตัว)

# ลำดับหน่วยเงินที่สลับด้วยปุ่ม currency
_CURRENCIES = ("divine", "exalted", "chaos")


class App:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        from .capture import set_dpi_aware
        from .repository import PriceRepository

        # สำคัญ: ตั้ง DPI aware "ก่อน" สร้าง Tk เสมอ ไม่งั้นบนจอ scale != 100%
        # พิกัด calibration/capture/overlay จะไม่ตรงกัน
        set_dpi_aware()
        self.repo = PriceRepository(league=config.league)
        self.overlay = Overlay(alpha=config.window_alpha)
        self.queue: queue.Queue = queue.Queue()
        self._engine = None
        self._hotkeys: HotkeyListener | None = None
        self._running = True
        self._showing = False       # กำลังโชว์ราคาค้างอยู่ไหม (one-shot toggle)
        self._busy = False          # กำลังสแกนอยู่ (กันกดซ้อน)
        self._last_rows = None       # ผลสแกนล่าสุด (re-render ตอนสลับหน่วยเงินโดยไม่ต้องสแกนใหม่)

    # ---- lifecycle ---------------------------------------------------------

    def run(self) -> None:
        self._start_hotkeys()
        # ดึงราคาครั้งแรกแบบ background (ไม่บล็อกหน้าจอ) + บอกสถานะจริงว่าได้/ไม่ได้
        # เดิมดึงแบบบล็อกก่อนเปิดจอ + ขึ้น "พร้อม" เสมอ ทำให้ถ้าดึงพลาดผู้ใช้ไม่รู้ ต้องไปกด refresh เอง
        self._status(f"กำลังดึงราคาครั้งแรก ({self.config.league})… รอสักครู่")
        self.overlay.root.after(50, self._poll)
        self.overlay.root.after(150, lambda: threading.Thread(target=self._initial_fetch, daemon=True).start())
        self.overlay.root.mainloop()

    def _initial_fetch(self) -> None:
        """ดึงราคาครั้งแรก + ตั้ง auto-refresh ทุก 30 นาที. รายงานผลจริงผ่าน status."""
        self.repo.start_auto_refresh()
        c = self.config
        n = self.repo.item_count
        if n > 0:
            self.queue.put(("status", f"พร้อม! ได้ราคา {n} รายการ — {c.toggle_key} แสดง/ซ่อน · "
                                       f"{c.currency_key} หน่วยเงิน · F8 ตั้งค่า"))
        else:
            self.queue.put(("status", "ดึงราคาไม่ได้ (เช็คเน็ต/ชื่อลีก) — กด F8 → 'ดึงราคาใหม่ตอนนี้'"))

    def _start_hotkeys(self) -> None:
        """สร้าง+เริ่ม HotkeyListener จากปุ่มใน config (เรียกซ้ำได้ตอนเปลี่ยนปุ่ม)."""
        if self._hotkeys is not None:
            self._hotkeys.stop()
            self._hotkeys.join(timeout=1.5)  # รอให้ตัวเก่าปล่อยปุ่มก่อน กันชนกับปุ่มเดิม
        c = self.config
        # ลงทะเบียน "ทางออกฉุกเฉิน" (เปิด Settings = F8, ออก = Ctrl+Alt+Q) ก่อนเสมอ —
        # ถ้าผู้ใช้เผลอตั้งปุ่มอื่นชน F8 ตัวที่ลงก่อนจะชนะ -> ยังเปิด Settings ไปแก้ได้
        self._hotkeys = HotkeyListener({
            _HK_SETTINGS: (0, _VK_F8, lambda: self.queue.put(("settings", None))),
            _HK_QUIT: (MOD_CONTROL | MOD_ALT, _VK_Q, lambda: self.queue.put(("quit", None))),
            _HK_TOGGLE: (0, key_name_to_vk(c.toggle_key, 0x78),
                         lambda: self.queue.put(("toggle", None))),
            _HK_CURRENCY: (0, key_name_to_vk(c.currency_key, 0x75),
                           lambda: self.queue.put(("currency", None))),
        })
        self._hotkeys.start()
        # ถ้าจองปุ่มไหนไม่ได้ (โปรแกรมอื่นจองไว้) เตือนผู้ใช้ แทนที่จะเงียบแล้วปุ่มตาย
        self.overlay.root.after(900, self._warn_failed_hotkeys)

    def _warn_failed_hotkeys(self) -> None:
        hk = self._hotkeys
        if hk is None or not hk.wait_ready(0):
            return
        names = {
            _HK_TOGGLE: self.config.toggle_key, _HK_CURRENCY: self.config.currency_key,
            _HK_SETTINGS: "F8", _HK_QUIT: "Ctrl+Alt+Q",
        }
        bad = [names.get(i, str(i)) for i in sorted(hk.failed)]
        if bad:
            self._status("ปุ่มลัดถูกโปรแกรมอื่นใช้อยู่: " + ", ".join(bad)
                         + " — ปิดโปรแกรมที่เปิดซ้อน/แอปอื่น หรือเปลี่ยนปุ่มใน F8")

    def stop(self) -> None:
        self._running = False
        self.repo.stop()
        if self._hotkeys:
            self._hotkeys.stop()
            # รอให้ thread ปุ่มลัด "ถอนทะเบียนปุ่ม (UnregisterHotKey)" ให้เสร็จก่อน —
            # ไม่งั้นปุ่ม global อาจค้างถูกจองไว้ ทำให้เปิดรอบหน้าจองปุ่มไม่ได้/ปิดไม่ได้
            self._hotkeys.join(timeout=1.5)
        self.overlay.destroy()

    # ---- queue pump (รันบน Tk thread) -------------------------------------

    def _poll(self) -> None:
        try:
            while True:
                action, payload = self.queue.get_nowait()
                if action == "toggle":
                    self._toggle()
                elif action == "currency":
                    self._cycle_currency()
                elif action == "settings":
                    self._open_settings()
                elif action == "quit":
                    self.stop()
                    return
                elif action == "show":
                    # ผลสแกนกลับมาแล้ว — วาดค้างไว้ (one-shot ไม่วน = ไม่กะพริบเลย)
                    self._busy = False
                    self._last_rows = payload
                    self._render_rows()
                    self._showing = True
                elif action == "status":
                    self._status(payload)
        except queue.Empty:
            pass
        if self._running:
            self.overlay.root.after(50, self._poll)

    # ---- actions -----------------------------------------------------------

    def _toggle(self) -> None:
        # toggle one-shot: โชว์อยู่ -> ซ่อน. ไม่งั้น -> สแกนทั้งจอ "ครั้งเดียว" แล้วค้างไว้ (ไม่วน = ไม่กะพริบ)
        if self._showing:
            self.overlay.clear()
            self._showing = False
            self._status(f"ซ่อนแล้ว ({self.config.currency}) — {self.config.toggle_key} แสดงราคา")
            return
        if self._busy:
            return
        self._busy = True
        self._status("กำลังอ่าน…")
        threading.Thread(target=self._scan_once, daemon=True).start()

    def _cycle_currency(self) -> None:
        cur = self.config.currency if self.config.currency in _CURRENCIES else "divine"
        self.config.currency = _CURRENCIES[(_CURRENCIES.index(cur) + 1) % len(_CURRENCIES)]
        self.config.save()
        if self._showing and self._last_rows is not None:
            self._render_rows()  # วาดใหม่จากผลเดิม ไม่ต้องสแกนใหม่
        self._status(f"หน่วยเงิน: {self.config.currency} — {self.config.currency_key} สลับ")

    # ---- settings ----------------------------------------------------------

    def _open_settings(self) -> None:
        from .settings import open_settings

        open_settings(self.overlay.root, self.config, self._apply_settings,
                      self._refresh_now, lambda: self.queue.put(("quit", None)))

    def _apply_settings(self, new: dict) -> None:
        c = self.config
        league_changed = new["league"] != c.league
        keys_changed = (
            new["toggle_key"] != c.toggle_key or new["currency_key"] != c.currency_key
        )
        c.league = new["league"]
        c.currency = new["currency"]
        c.toggle_key = new["toggle_key"]
        c.currency_key = new["currency_key"]
        c.window_alpha = new["window_alpha"]
        c.save()

        self.overlay.set_alpha(c.window_alpha)
        if keys_changed:
            self._start_hotkeys()  # ลงทะเบียนปุ่มใหม่
        if league_changed:
            self.repo.league = c.league
            self._refresh_now()
        elif self._showing and self._last_rows is not None:
            self._render_rows()  # อัปเดตหน่วยเงินที่อาจเปลี่ยน
        else:
            self._status(f"บันทึกการตั้งค่าแล้ว ({c.currency})")

    def _refresh_now(self) -> None:
        """ดึงราคาใหม่จาก poe.ninja ทันที (ไม่ต้องรอรอบ 30 นาที). เรียกจากปุ่มใน Settings."""
        self._status(f"กำลังดึงราคาลีก {self.config.league} ใหม่…")
        threading.Thread(target=self._refetch, daemon=True).start()

    def _refetch(self) -> None:
        try:
            snap = self.repo.fetch()
            self.queue.put(("status", f"ดึงราคาใหม่แล้ว ({snap.item_count} รายการ) — "
                                       f"{self.config.toggle_key} แสดงราคา"))
        except Exception as exc:
            self.queue.put(("status", f"ดึงราคาไม่ได้: {exc}"))

    # ---- worker (รันบน background thread) ----------------------------------

    def _scan_once(self) -> None:
        """สแกนทั้งจอ "ครั้งเดียว" แล้วส่งผลกลับ Tk thread. ไม่วนลูป ไม่ล้างจอซ้ำ = ไม่กะพริบ."""
        if self._engine is None:
            try:
                from .ocr import create_default_engine

                self._engine = create_default_engine()
            except Exception as exc:
                self._busy = False
                self.queue.put(("status", f"OCR ใช้ไม่ได้: {exc}"))
                return
        try:
            from .capture import capture_screen
            from .scan import scan_lines

            rows = scan_lines(self.repo, self._engine.recognize(capture_screen()))
            self._dump_debug(rows)
            self.queue.put(("show", rows))
        except Exception as exc:
            self._busy = False
            self.queue.put(("status", f"สแกนพลาด: {exc}"))

    def _dump_debug(self, rows) -> None:
        """เขียนผลสแกนล่าสุดลง last_scan.txt (เขียนทับทุกครั้ง) — ไว้ดูว่า OCR อ่านอะไร
        และ match อะไร เวลาราคาบางตัวไม่ขึ้น. อยู่ที่ %LOCALAPPDATA%\\PoePriceHelper\\last_scan.txt"""
        try:
            import os

            from .config import data_dir

            lines = []
            for r in rows:
                if r.matched:
                    e = r.result.entry
                    val = "no-market" if not e.has_market_data else f"{e.exalted_value:g}ex"
                    tag = f"-> {r.result.key} [{r.result.method}] {val}"
                elif r.result.is_gem:
                    tag = "-> gem unknown (?)"
                else:
                    tag = "-> MISS"
                lines.append(f"{r.line.text!r}  {tag}")
            with open(os.path.join(data_dir(), "last_scan.txt"), "w", encoding="utf-8") as f:
                f.write(f"OCR อ่านได้ {len(rows)} บรรทัด:\n\n" + "\n".join(lines) + "\n")
        except Exception:
            pass

    # ---- rendering (Tk thread) ---------------------------------------------

    def _render_rows(self) -> None:
        items = self._rows_to_items(self._last_rows, None, self.config.currency)
        self.overlay.render(items)
        priced = sum(1 for r in self._last_rows if r.matched and r.result.entry.has_market_data)
        self._status(f"เจอ {priced} ราคา ({self.config.currency}) — {self.config.toggle_key} ซ่อน · "
                     f"{self.config.currency_key} หน่วยเงิน")

    def _rows_to_items(self, rows, region, unit) -> list[OverlayItem]:
        """แปลงผลสแกนเป็นป้ายราคา — วาด "ข้างขวาของแต่ละชิ้น" (ใช้ได้ทั้ง list และ grid).
        พิกัด OCR อิงมุมซ้ายบนของภาพที่จับ จึงบวก offset ของ region (ถ้าล็อกพื้นที่ไว้)
        ให้กลายเป็นพิกัดจอจริง."""
        from .specials import match_special

        off_x, off_y = (region[0], region[1]) if region is not None else (0, 0)
        items: list[OverlayItem] = []
        for r in rows:
            bx, by, bw, bh = r.line.bbox
            x = off_x + bx + bw + 8       # ชิดขวาของชื่อชิ้นนั้น
            y = off_y + by + bh / 2
            # ของพิเศษ/มุกปั่น ๆ (เช่น Random Currency -> กระจก, Unique -> Mageblood)
            # เช็คก่อนราคาปกติ เพราะชื่อพวกนี้ไม่มีใน poe.ninja อยู่แล้ว
            special = match_special(r.line.text)
            if special is not None:
                items.append(OverlayItem(x, y, special.text, unit=special.icon,
                                         color=special.color))
                continue
            if r.matched:
                e = r.result.entry
                if not e.has_market_data:
                    items.append(OverlayItem(x, y, "?", color="#9aa0a6"))
                    continue
                value = r.total(unit)
                qty = f"{r.quantity}x " if r.quantity > 1 else ""
                # text = ตัวเลขล้วน, unit = ไว้ให้ overlay เลือกไอคอน (ไม่โชว์เป็นตัวอักษร)
                items.append(OverlayItem(x, y, f"{qty}{value:.4g}", unit=unit))
            elif r.result.is_gem:
                items.append(OverlayItem(x, y, "?", color="#9aa0a6"))
        return items

    # ---- ui helper ---------------------------------------------------------

    def _status(self, text: str) -> None:
        # วาดสถานะมุมซ้ายบน (ทับของเดิมในรอบ render ถัดไปจะถูกล้าง แต่สถานะ
        # นอกพื้นที่สแกนจึงไม่ค่อยโดนทับ). ใช้ item เดียวเรียบ ๆ.
        self.overlay.canvas.delete("status")
        self.overlay.canvas.create_text(
            12, 12, text=f"PoE Price Check · {text}", anchor="nw",
            fill="#ffd56b", font=("Segoe UI", 10, "bold"), tags="status",
        )


_MUTEX_NAME = "PoePriceCheck_SingleInstance_Mutex_v1"
_ERROR_ALREADY_EXISTS = 183


def _acquire_single_instance():
    """จองชื่อ mutex ของ Windows. คืน handle ถ้าเป็นอินสแตนซ์แรก; คืน None ถ้ามี
    โปรแกรมเปิดอยู่แล้ว. ป้องกันเปิดซ้อน — ซึ่งทำให้ตัวที่ 2+ จองปุ่มลัด (รวม Ctrl+Alt+Q)
    ไม่ได้เลย แล้วกลายเป็นปิดไม่ได้ ต้องไปฆ่าใน Task Manager."""
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle:
        return True  # จอง mutex ไม่ได้ด้วยเหตุผลแปลก ๆ -> อย่าบล็อก ปล่อยให้รันต่อ
    if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
        return None
    return handle


def _warn_already_running() -> None:
    import ctypes

    ctypes.windll.user32.MessageBoxW(
        None,
        "PoE Price Check กำลังเปิดอยู่แล้ว\n\n"
        "ปิดตัวเดิมก่อน แล้วค่อยเปิดใหม่ — กด Ctrl+Alt+Q "
        "หรือกด F8 เพื่อเข้าตั้งค่าแล้วปิดโปรแกรม",
        "PoE Price Check",
        0x40,  # MB_ICONINFORMATION
    )


def main() -> int:
    import argparse
    import os
    import sys

    # โหมด --windowed (ไม่มี console) ทำให้ sys.stdout/stderr เป็น None -> print() จะพัง
    # จึง redirect ไปไฟล์ log แทน (อยู่ที่ %LOCALAPPDATA%\PoePriceHelper\log.txt) เผื่อ debug
    if sys.stdout is None or sys.stderr is None:
        try:
            from .config import data_dir
            logf = open(os.path.join(data_dir(), "log.txt"), "w", encoding="utf-8")
        except Exception:
            logf = open(os.devnull, "w")
        if sys.stdout is None:
            sys.stdout = logf
        if sys.stderr is None:
            sys.stderr = logf

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(prog="poe_price.app", description="PoE2 price overlay")
    parser.add_argument("--league", help="ระบุชื่อลีก (ทับค่าใน config)")
    parser.add_argument("--selftest", action="store_true",
                        help="ทดสอบ capture+OCR ครั้งเดียวแล้วออก (เช็คว่า winrt ใช้ได้ โดยเฉพาะในไฟล์ .exe)")
    args = parser.parse_args()

    if args.selftest:
        from .capture import capture_screen, set_dpi_aware
        from .ocr import create_default_engine
        set_dpi_aware()
        try:
            res = create_default_engine().recognize(capture_screen())
            print(f"SELFTEST OK: OCR อ่านได้ {len(res.lines)} บรรทัด")
            return 0
        except Exception as exc:
            print(f"SELFTEST FAIL: {exc}")
            return 1

    # กันเปิดซ้อน: ถ้ามีตัวเปิดอยู่แล้ว เด้งเตือนสั้น ๆ แล้วออก (อย่าเปิดตัวที่ 2
    # ที่จองปุ่มลัดไม่ได้ -> ปิดไม่ได้ -> ค้างใน Task Manager). ถือ handle ไว้ทั้งโปรเซส
    _mutex = _acquire_single_instance()
    if _mutex is None:
        print("มีโปรแกรมเปิดอยู่แล้ว — ไม่เปิดซ้อน")
        _warn_already_running()
        return 0

    config = AppConfig.load()
    if args.league:
        config.league = args.league

    print(f"league={config.league}  (สแกนทั้งจอ)")
    print(f"เปิด overlay — {config.toggle_key} แสดง/ซ่อน · {config.currency_key} หน่วยเงิน · "
          f"F8 ตั้งค่า · Ctrl+Alt+Q ออก")
    App(config).run()

    # การันตีปิดสนิท: หลัง mainloop จบ บังคับจบโปรเซสทันที กัน native thread (message
    # loop ของปุ่มลัด ฯลฯ) ค้างจน .exe ไม่ยอมหายไปจาก Task Manager
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    os._exit(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
