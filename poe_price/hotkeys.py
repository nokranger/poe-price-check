"""Global hotkeys ผ่าน RegisterHotKey (ctypes ล้วน) — ทำงานแม้โฟกัสอยู่ที่เกม.

ปลอดภัย/โปร่งใส: ใช้ RegisterHotKey ของ Windows ตามปกติ (ไม่ใช่ keyboard hook
ระดับล่างที่ดักทุกปุ่ม) จึงเห็นเฉพาะปุ่มที่ลงทะเบียนไว้เท่านั้น ไม่แอบอ่านคีย์อื่น.

หมายเหตุ: RegisterHotKey จะ "กิน" ปุ่มที่ลงทะเบียน (เกมจะไม่ได้รับ) — เลยควรเลือก
ปุ่มที่ไม่ชนกับ keybind ในเกม. ค่าเริ่มต้น F9 (แสดง/ซ่อน) และ F6 (สลับหน่วยเงิน).
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_MOD_NOREPEAT = 0x4000

# modifier flags (รวมกับ vk ตอนลงทะเบียน)
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004

VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75

# ชื่อปุ่ม -> virtual-key code (สำหรับให้ UI ตั้งค่าปุ่มเลือกได้).
# F1-F12 + ปุ่มที่เกมแทบไม่ผูก (Insert/Delete/Home/End/PgUp/PgDn) เหมาะกับ overlay.
KEY_NAMES: dict[str, int] = {f"F{i}": 0x70 + (i - 1) for i in range(1, 13)}
KEY_NAMES.update({
    "Insert": 0x2D, "Delete": 0x2E, "Home": 0x24,
    "End": 0x23, "PgUp": 0x21, "PgDn": 0x22,
})
# ลำดับสำหรับโชว์ใน dropdown
KEY_ORDER: list[str] = [f"F{i}" for i in range(1, 13)] + ["Insert", "Delete", "Home", "End", "PgUp", "PgDn"]
VK_TO_NAME: dict[int, str] = {vk: name for name, vk in KEY_NAMES.items()}


def key_name_to_vk(name: str, default: int) -> int:
    return KEY_NAMES.get(name, default)

_user32 = ctypes.windll.user32
_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_kernel32 = ctypes.windll.kernel32


class HotkeyListener(threading.Thread):
    """รับ global hotkey แล้วเรียก callback. callback ถูกเรียกบน thread นี้ —
    ผู้ใช้ควร marshal กลับไป UI thread เอง (เช่นผ่าน queue)."""

    def __init__(self, bindings: dict[int, tuple[int, int, callable]]) -> None:
        """bindings: { id -> (modifiers, virtual_key, callback) }
        modifiers = OR ของ MOD_ALT/MOD_CONTROL/MOD_SHIFT (0 = ไม่มี)."""
        super().__init__(daemon=True)
        self._bindings = bindings
        self._thread_id = 0
        self._ready = threading.Event()
        self.failed: set[int] = set()  # id ปุ่มที่จองไม่ได้ (ถูกโปรแกรมอื่นจองไปแล้ว)

    def wait_ready(self, timeout: float = 1.5) -> bool:
        """รอจน thread ลงทะเบียนปุ่มเสร็จ (เพื่ออ่าน .failed ได้ถูกต้อง)."""
        return self._ready.wait(timeout)

    def run(self) -> None:
        self._thread_id = _kernel32.GetCurrentThreadId()
        for hotkey_id, (mods, vk, _) in self._bindings.items():
            if not _user32.RegisterHotKey(None, hotkey_id, mods | _MOD_NOREPEAT, vk):
                self.failed.add(hotkey_id)
                print(f"[hotkeys] ลงทะเบียนปุ่ม id={hotkey_id} ไม่ได้ (อาจมีโปรแกรมอื่นใช้อยู่)")
        self._ready.set()

        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _WM_HOTKEY:
                binding = self._bindings.get(int(msg.wParam))
                if binding is not None:
                    try:
                        binding[2]()
                    except Exception as exc:
                        print(f"[hotkeys] callback error: {exc}")

        for hotkey_id in self._bindings:
            _user32.UnregisterHotKey(None, hotkey_id)

    def stop(self) -> None:
        self._ready.wait(timeout=2.0)
        if self._thread_id:
            _user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)
