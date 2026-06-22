"""Fuzzy matching: จับคู่ชื่อไอเทม (ที่อาจอ่านเพี้ยนจาก OCR) เข้ากับ price key.

ลำดับการ resolve (ตรงกับต้นฉบับ C# ScanEngine):
  1. Uncut gem  — ปักหมุดด้วย "ชนิด + เลเวล" แบบเป๊ะ ไม่ใช้ fuzzy เด็ดขาด
                  (เจมต่างเลเวลราคาต่างกันหลายเท่า อ่านเลขเพี้ยนตัวเดียวก็พังได้)
  2. exact      — ชื่อ normalize แล้วตรงกับ key เป๊ะ
  3. prefix     — ชื่อยาว ≥ 10 ตัว และเป็นต้นขึ้นต้นของ key (เลือก key ที่สั้นสุด)
  4. fuzzy      — ชื่อยาว ≥ 6 ตัว, ใช้ Levenshtein หา key ที่คล้ายสุดเหนือ threshold

ทุกอย่างเป็นฟังก์ชันบริสุทธิ์ ทดสอบได้แบบ offline ไม่ต้องมี snapshot จริง.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import PriceEntry, PriceSnapshot
from .normalizer import normalize

# ความคล้ายขั้นต่ำ (1 - editDistance/maxLen) ที่ยอมรับว่าเป็น fuzzy match.
# 0.84 = ปล่อยให้ผิดได้ ~2 ตัวบนชื่อยาว 12+ ตัว, 1 ตัวบนชื่อ ~6 ตัว.
FUZZY_THRESHOLD = 0.84
# คะแนน ≥ ค่านี้ เชื่อถือได้เท่า exact (lock ทันทีไม่ต้องอ่านซ้ำ).
HIGH_CONFIDENCE_THRESHOLD = 0.92

_MIN_PREFIX_LEN = 10
_MIN_FUZZY_LEN = 6

_GEM_TYPE = re.compile(r"\b(skill|spirit|support)\b")
_GEM_LEVEL = re.compile(r"\blevel\s+(\d+)\b")


@dataclass(frozen=True, slots=True)
class MatchResult:
    """ผลการจับคู่ชื่อ -> ราคา.

    - matched()  : เจอราคาไหม
    - key        : price key ที่จับได้ (ใช้ key นี้เก็บแทน OCR ที่ noisy เพื่อให้ lock นิ่ง)
    - entry      : ราคา (None ถ้าไม่เจอ)
    - exact      : เชื่อถือได้เท่า exact หรือไม่ (fuzzy คะแนนสูงก็ True)
    - is_gem     : ถูกระบุว่าเป็น uncut gem
    - method     : "gem" | "exact" | "prefix" | "fuzzy" | "gem-unknown" | "miss"
    - score      : คะแนนความคล้าย (เฉพาะ fuzzy), ไม่งั้น None
    """

    key: str | None
    entry: PriceEntry | None
    exact: bool = False
    is_gem: bool = False
    method: str = "miss"
    score: float | None = None

    def matched(self) -> bool:
        return self.entry is not None


def levenshtein(a: str, b: str) -> int:
    """edit distance แบบสองแถว (ประหยัดหน่วยความจำ) — ตรงกับต้นฉบับ."""
    prev = list(range(len(b) + 1))
    curr = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        curr[0] = i
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            cost = 0 if ai == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev
    return prev[len(b)]


def best_fuzzy(
    keys_by_length: dict[int, list[str]],
    name: str,
    threshold: float = FUZZY_THRESHOLD,
) -> tuple[str, float] | None:
    """หา key ที่คล้าย name สุดด้วย Levenshtein, คืน (key, score) หรือ None.

    เช็คเฉพาะ key ที่ความยาวต่างจาก name ไม่เกิน ±3 (โดยใช้ index ตามความยาว)
    — ถูกกว่ามากเพราะไม่ต้องวนทุก key และความยาวต่างมากยังไงก็ไม่ใกล้.
    ต้องได้คะแนน "มากกว่า" threshold จริง ๆ ถึงชนะ.
    """
    best: str | None = None
    best_score = threshold
    for length in range(max(0, len(name) - 3), len(name) + 4):
        keys = keys_by_length.get(length)
        if not keys:
            continue
        for key in keys:
            dist = levenshtein(name, key)
            score = 1.0 - dist / max(len(name), len(key))
            if score > best_score:
                best_score = score
                best = key
    return (best, best_score) if best is not None else None


def try_resolve_gem_key(normalized_name: str) -> tuple[bool, str | None]:
    """ตรวจว่าเป็น uncut gem ไหม + ปักหมุด key.

    คืน (is_gem, key):
      - is_gem=True, key="uncut <type> gem level <n>"  เมื่ออ่านชนิดและเลเวลได้ครบ
      - is_gem=True, key=None                          เป็นเจมแต่อ่านเลเวลไม่ได้ -> โชว์ '?'
      - is_gem=False, key=None                         ไม่ใช่เจม

    เกณฑ์: มีคำว่า "gem" + คำชนิด (skill/spirit/support). ตัวที่ใช้แยกเจมคือ
    "ชนิด" กับ "gem" เท่านั้น คำประกอบอื่นอ่านเพี้ยน ("uncot", "levei") ไม่ทำให้พลาด.
    """
    if "gem" not in normalized_name:
        return False, None
    type_match = _GEM_TYPE.search(normalized_name)
    if not type_match:
        return False, None
    level_match = _GEM_LEVEL.search(normalized_name)
    if level_match:
        return True, f"uncut {type_match.group(1)} gem level {level_match.group(1)}"
    return True, None


def resolve(snapshot: PriceSnapshot, raw_name: str) -> MatchResult:
    """จับคู่ชื่อดิบ (จะ normalize ให้เอง) เข้ากับราคาใน snapshot ตามลำดับ
    gem -> exact -> prefix -> fuzzy. คืน MatchResult เสมอ (miss ก็มี result)."""
    name = normalize(raw_name)
    prices = snapshot.prices

    # 1) uncut gem — ปักหมุดเป๊ะ ไม่ fuzzy
    is_gem, gem_key = try_resolve_gem_key(name)
    if is_gem:
        if gem_key is not None and gem_key in prices:
            return MatchResult(gem_key, prices[gem_key], exact=True, is_gem=True, method="gem")
        # เป็นเจมแต่ปักราคาไม่ได้ -> '?' ไม่ตกไป fuzzy
        return MatchResult(None, None, exact=False, is_gem=True, method="gem-unknown")

    # 2) exact
    entry = prices.get(name)
    if entry is not None:
        return MatchResult(name, entry, exact=True, method="exact")

    # 3) prefix (เฉพาะชื่อยาวพอ)
    if len(name) >= _MIN_PREFIX_LEN:
        candidates = [k for k in prices if k.startswith(name)]
        if candidates:
            prefix_key = min(candidates, key=len)
            return MatchResult(prefix_key, prices[prefix_key], exact=False, method="prefix")

    # 4) fuzzy (เฉพาะชื่อยาวพอ)
    if len(name) >= _MIN_FUZZY_LEN:
        found = best_fuzzy(snapshot.keys_by_length, name)
        if found is not None:
            fuzzy_key, score = found
            return MatchResult(
                fuzzy_key,
                prices[fuzzy_key],
                exact=score >= HIGH_CONFIDENCE_THRESHOLD,
                method="fuzzy",
                score=score,
            )

    return MatchResult(None, None, method="miss")
