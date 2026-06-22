"""PriceRepository — เก็บราคาในหน่วยความจำ + cache + auto-refresh.

หน้าที่:
  - ดึงทุก exchange type พร้อมกัน (concurrent) แล้ว merge เป็น snapshot เดียว
  - เผยแพร่ snapshot แบบ atomic (อ่านระหว่าง refresh ไม่เห็นข้อมูลครึ่ง ๆ กลาง ๆ)
  - auto-refresh ทุก 30 นาทีด้วย background thread
  - ค้นราคาด้วยชื่อไอเทม (normalize ให้อัตโนมัติ)

ใช้ standard library ล้วน: threading + concurrent.futures.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .client import EXCHANGE_TYPES, fetch_type
from .matcher import MatchResult, resolve
from .models import PriceEntry, PriceSnapshot

DEFAULT_REFRESH_SECONDS = 30 * 60  # 30 นาที ตามต้นฉบับ
_EMPTY = PriceSnapshot(prices={}, keys_by_length={}, fetched_at=None)


class PriceRepository:
    def __init__(
        self,
        league: str = "Runes of Aldur",
        timeout: float = 30.0,
        types: tuple[str, ...] | None = None,
    ) -> None:
        self.league = league
        self.timeout = timeout
        self.types = types if types is not None else EXCHANGE_TYPES
        self._lock = threading.Lock()
        self._snapshot = _EMPTY
        self._generation = 0
        self._timer: threading.Timer | None = None
        self._on_update: list = []

    # ---- อ่านสถานะ (thread-safe) -------------------------------------------

    @property
    def snapshot(self) -> PriceSnapshot:
        with self._lock:
            return self._snapshot

    @property
    def generation(self) -> int:
        """เพิ่มขึ้น 1 ทุกครั้งที่ refresh สำเร็จ — ใช้เช็คว่าราคาเปลี่ยนไหม
        (มีประโยชน์ตอนทำ OCR cache ในอนาคต)."""
        with self._lock:
            return self._generation

    @property
    def item_count(self) -> int:
        return self.snapshot.item_count

    @property
    def last_fetched_at(self) -> float | None:
        return self.snapshot.fetched_at

    def on_update(self, callback) -> None:
        """ลงทะเบียน callback ที่จะถูกเรียกหลัง refresh สำเร็จทุกครั้ง.
        callback ถูกเรียกบน background thread — ฝั่ง UI ต้อง marshal เอง."""
        self._on_update.append(callback)

    # ---- ดึงราคา -----------------------------------------------------------

    def fetch(self) -> PriceSnapshot:
        """ดึงทุก type พร้อมกัน, merge, แล้ว publish snapshot ใหม่. คืน snapshot นั้น.
        type ไหน fail จะถูกข้าม (log) ไม่ทำให้ทั้งก้อนพัง."""
        with ThreadPoolExecutor(max_workers=max(1, len(self.types))) as pool:
            results = list(pool.map(self._safe_fetch_type, self.types))

        merged: dict[str, PriceEntry] = {}
        for partial in results:
            merged.update(partial)

        # ถ้าดึงรอบนี้ไม่ได้อะไรเลย (น่าจะเน็ตหลุดชั่วคราว) แต่เคยมีราคาแล้ว -> คงราคาเดิมไว้
        # ไม่งั้น auto-refresh ที่พลาดจะทำให้ราคาหายหมดจนกว่าจะถึงรอบถัดไป
        if not merged and self.item_count > 0:
            print("[PriceRepository] refresh ได้ 0 รายการ (เน็ตหลุด?) — คงราคาเดิมไว้")
            return self.snapshot

        keys_by_length: dict[int, list[str]] = {}
        for key in merged:
            keys_by_length.setdefault(len(key), []).append(key)

        snapshot = PriceSnapshot(
            prices=merged,
            keys_by_length=keys_by_length,
            fetched_at=time.time(),
        )
        with self._lock:
            self._snapshot = snapshot
            self._generation += 1

        for callback in list(self._on_update):
            try:
                callback(snapshot)
            except Exception as exc:  # callback พังไม่ควรทำให้ refresh พัง
                print(f"[PriceRepository] on_update callback failed: {exc}")
        return snapshot

    def _safe_fetch_type(self, exchange_type: str) -> dict[str, PriceEntry]:
        try:
            return fetch_type(self.league, exchange_type, self.timeout)
        except Exception as exc:
            print(f"[PriceRepository] {exc}")
            return {}

    # ---- auto-refresh ------------------------------------------------------

    def start_auto_refresh(self, interval: float = DEFAULT_REFRESH_SECONDS) -> None:
        """ดึงทันที 1 ครั้ง แล้วตั้งให้ดึงซ้ำทุก ๆ interval วินาทีเบื้องหลัง."""
        self.fetch()
        self._schedule(interval)

    def _schedule(self, interval: float) -> None:
        timer = threading.Timer(interval, self._tick, args=(interval,))
        timer.daemon = True
        with self._lock:
            self._timer = timer
        timer.start()

    def _tick(self, interval: float) -> None:
        try:
            self.fetch()
        finally:
            self._schedule(interval)

    def stop(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    # ---- ค้นราคา -----------------------------------------------------------

    def get(self, name: str) -> PriceEntry | None:
        """ค้นราคาแบบ exact ด้วยชื่อไอเทม (จะ normalize ให้เอง). คืน None ถ้าไม่เจอเป๊ะ.
        ถ้าต้องการให้ทนชื่อเพี้ยน (OCR) ใช้ match() แทน."""
        from .normalizer import normalize

        return self.snapshot.prices.get(normalize(name))

    def match(self, name: str) -> MatchResult:
        """จับคู่ชื่อไอเทมเข้ากับราคาแบบ fuzzy: gem -> exact -> prefix -> fuzzy.
        คืน MatchResult เสมอ (แม้ miss) — ดู .matched(), .entry, .method, .exact."""
        return resolve(self.snapshot, name)

    # ---- context manager ---------------------------------------------------

    def __enter__(self) -> PriceRepository:
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
