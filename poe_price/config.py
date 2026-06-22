"""ตั้งค่าโปรแกรม (league, พื้นที่จับภาพ ฯลฯ) — เก็บเป็น JSON ด้วย stdlib ล้วน.

เก็บไว้ที่ %LOCALAPPDATA%\\PoePriceHelper\\config.json (ถ้าไม่มีก็ใช้โฮมไดเรกทอรี)
เพื่อให้ค่า calibration อยู่รอดข้ามการอัปเดตเวอร์ชัน.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

APP_NAME = "PoePriceHelper"


def data_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def config_path() -> str:
    return os.path.join(data_dir(), "config.json")


@dataclass
class AppConfig:
    league: str = "Runes of Aldur"  # ลีกปัจจุบัน (poe.ninja slug: runesofaldur)
    # พื้นที่จับภาพ (left, top, width, height); None = ยังไม่ได้ calibrate
    region: tuple[int, int, int, int] | None = None
    scan_interval: float = 1.0          # วินาทีต่อรอบสแกน
    currency: str = "divine"            # หน่วยที่จะแสดง: "divine" | "exalted" | "chaos"
    show_unmatched: bool = False        # โชว์บรรทัดที่จับคู่ไม่ได้ด้วยไหม
    window_alpha: int = 190             # ความโปร่งแสงของ overlay (0-255; มาก=ทึบ)
    # ปุ่มลัด (ชื่อปุ่ม เช่น "F9") — ตั้งได้ผ่านหน้า Settings.
    # default เลี่ยง F5 (มักชนปุ่มในเกม) ใช้ F9/F6
    toggle_key: str = "F9"
    currency_key: str = "F6"

    def save(self, path: str | None = None) -> None:
        path = path or config_path()
        data = asdict(self)
        if self.region is not None:
            data["region"] = list(self.region)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | None = None) -> "AppConfig":
        path = path or config_path()
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return cls()
        region = data.get("region")
        cfg = cls(
            league=data.get("league", "Runes of Aldur"),
            region=tuple(region) if region else None,
            scan_interval=float(data.get("scan_interval", 1.0)),
            currency=data.get("currency", "divine"),
            show_unmatched=bool(data.get("show_unmatched", False)),
            window_alpha=int(data.get("window_alpha", 190)),
            toggle_key=data.get("toggle_key", "F9"),
            currency_key=data.get("currency_key", "F6"),
        )
        return cfg
