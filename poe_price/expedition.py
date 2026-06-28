"""ข่าวลือ Expedition Logbook (Island Rumours) — lookup แมพ/มอด/เทียร์.

ไม่เกี่ยวกับราคา: เป็น "ตารางอ้างอิง" ช่วยตัดสินใจว่าจะลง Expedition ข่าวลือไหนดี.
เวลาเอาเมาส์ชี้ไอคอนออกเรือบน Logbook เกมจะโชว์ชื่อข่าวลือ (เช่น "Sulphite!",
"Somethin' fishy...") — โมดูลนี้จับชื่อนั้นแล้วบอกว่าไป map ไหน / มอดเด่นอะไร /
เทียร์ความคุ้ม (S/A/B/C/D/F).

ดีไซน์ให้คงคอนเซ็บเดิม:
  - ข้อมูล snapshot เก็บ offline ล้วน (ไม่ต่อเน็ตเพิ่ม, zero-dep) — อัปเดตได้ในแพทช์
  - จับชื่อทน OCR เพี้ยน: normalize -> exact -> fuzzy (Levenshtein) ใช้ matcher
    ตัวเดียวกับฝั่งราคา. ตัดวงเล็บต่อท้าย เช่น "(Grand Expedition)" ออกก่อนเทียบ

เครดิตข้อมูล: ตารางจัดเทียร์โดยคอมมูนิตี้ผู้เล่นไทย (Google Sheet)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .matcher import levenshtein
from .normalizer import normalize

# เกณฑ์ fuzzy — ข่าวลือมีไม่กี่ชื่อและต่างกันชัด ตั้งหลวมกว่าฝั่งราคาได้นิดหน่อย
_FUZZY_THRESHOLD = 0.80

# ตัดส่วนต่อท้ายในวงเล็บ เช่น "Sulphite!(Grand Expedition)" / "A good fellow ( UNIQUE MAP)"
_PAREN = re.compile(r"\s*\(.*?\)\s*")


@dataclass(frozen=True, slots=True)
class Rumour:
    name: str                       # ชื่อข่าวลือ (อ่านง่าย ไว้โชว์)
    map: str                        # แมพที่จะได้
    mods: str                       # มอด/รางวัลเด่น
    rating: str                     # เทียร์ความคุ้ม: S+/S/A+/A/B+/B/C/D/F
    aliases: tuple[str, ...] = ()   # ชื่อที่เกมโชว์จริง (ถ้าต่างจาก name) ไว้ช่วย match


# (ชื่อข่าวลือ, แมพ, มอดเด่น, เทียร์, (ชื่อที่เกมโชว์เพิ่มเติม...)) — snapshot จากชีตคอมมูนิตี้.
# aliases สำคัญตรงที่เกมโชว์ "ชื่อเล่น" ไม่ตรงกับชื่อในชีต เช่น It's Warm -> "Warm but risky".
# ถ้าเจอข่าวลือไหนยัง detect ไม่ได้ ให้เพิ่มข้อความที่เกมโชว์จริงลงใน aliases ของอันนั้น.
_RAW: tuple[tuple, ...] = (
    ("Almost Paradise", "Untainted Paradise", "Exp", "C"),
    ("A Good Fellow", "Moment of Zen", "Seer", "C"),
    ("All That Glitters", "Castaway", "Gold", "A"),
    ("Bleak and Awful", "Barren Atoll", "Strongbox", "F"),
    ("Cold as Ice", "Frigid Bluffs", "Old Expedition", "A+"),
    ("Endless Cliffs", "Craggy Peninsula", "Rarity / Rogue Exiles", "A"),
    ("End of the Circle", "Sprawling Jungle", "Medved (Boss)", "B"),
    ("Fallen Stars", "Moor", "Runestones", "S+"),
    # OCR อ่านบรรทัดนี้ผิดเป็น "It's at lust" คงที่ทุก scale (2x/3x/4x) เพราะฟอนต์ลายมือ
    # -> ดักด้วย alias ตรง ๆ. ปลอดภัยเพราะจับเฉพาะในช่วง Island Rumours (ดู find_in_lines)
    ("It's Dry at Least", "Sloughed Gully", "Monster Effectiveness", "D", ("It's at Lust",)),
    ("It's Warm", "Lush Island", "Exp / Beyond / Hoards", "B", ("Warm but Risky",)),
    ("Last to Fall", "Mournful Cliffside", "Vorana (Boss)", "B", ("The Last to Fall",)),
    ("Nothing to Drink", "Stagnant Basin", "Oil", "A"),
    ("Origin of the Fall", "Obscure Island", "Olroth (Boss)", "A"),
    ("Reflective Waters", "Lake of Kalandra", "Ring Bases", "A"),
    ("Something Fishy", "Bleached Shoals", "Gold", "B+", ("Somethin' Fishy",)),
    ("Sulphite!", "Scorched Cay", "Increased Rarity", "A"),
    ("Stardrinker", "Secluded Temple", "Uhtred (Boss)", "B"),
    # "Unknown ruins" เป็น minim-heavy (n/m/u/w/r เหมือนกันในฟอนต์ลายมือ) OCR เลยอ่าน
    # มั่วเป็น "Uwkwoww miws" คงที่ทุกครั้ง -> ดักด้วย alias ตรง ๆ (กู้ด้วย fuzzy/token ไม่ได้)
    ("Unknown Ruins", "Exhumed Ruins", "Precursor Leylines", "B", ("Uwkwoww Miws",)),
    ("Wild, Roaming Free", "Grazed Prairie", "Azmeri Spirits", "D", ("Wild Roaming Free",)),
)

RUMOURS: tuple[Rumour, ...] = tuple(Rumour(*row) for row in _RAW)


def _key(text: str) -> str:
    """normalize + ตัดวงเล็บต่อท้าย -> คีย์ไว้เทียบ."""
    return normalize(_PAREN.sub(" ", text))


# index: คีย์ที่ normalize แล้ว (name + aliases ทั้งหมด) -> Rumour
_INDEX: dict[str, Rumour] = {}
for _r in RUMOURS:
    for _label in (_r.name, *_r.aliases):
        _INDEX[_key(_label)] = _r

# ความยาวคีย์ขั้นต่ำที่ยอมให้จับแบบ "วลีย่อย" — กันคำสั้น ๆ ไปแมตช์มั่ว
_MIN_CONTAIN = 6

# คำพื้น ๆ ที่ไม่ช่วยแยกข่าวลือ — ตัดทิ้งตอนทำ token matching
_STOPWORDS = {"its", "it", "the", "and", "but", "for", "you", "all", "that", "this"}
# token ต้องยาว >= นี้ + คล้ายกัน >= นี้ ถึงนับว่า "คำเด่นตรงกัน" (กัน false positive ตอนเช็คราคา)
_TOKEN_MIN_LEN = 4
_TOKEN_RATIO = 0.80
# เกณฑ์หลวมกว่า ใช้เฉพาะตอน region-anchored (รู้แน่ว่าเป็นบรรทัดข่าวลือ) — กันคำสั้นอย่าง
# "warm" หลุดเพราะ OCR พลาดตัวเดียว (เช่น "Worm"~"warm"=0.75). ปลอดภัยเพราะไม่ทำงานนอกหน้า Logbook
_TOKEN_RATIO_REGION = 0.72


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return 1.0 - levenshtein(a, b) / max(len(a), len(b))


def _tokens(key: str) -> list[str]:
    """แตกเป็นคำเด่น (ยาวพอ + ไม่ใช่คำพื้น ๆ) ไว้จับทีละคำ."""
    return [t for t in key.split() if len(t) >= _TOKEN_MIN_LEN and t not in _STOPWORDS]


# คำเด่นของแต่ละข่าวลือ (จาก name + aliases) — precompute ไว้
_RUMOUR_TOKENS: list[tuple[set[str], Rumour]] = []
for _r in RUMOURS:
    _toks: set[str] = set()
    for _label in (_r.name, *_r.aliases):
        _toks.update(_tokens(_key(_label)))
    if _toks:
        _RUMOUR_TOKENS.append((_toks, _r))


def _token_match(key: str, ratio: float = _TOKEN_RATIO) -> Rumour | None:
    """จับแบบทีละคำเด่น — ทน OCR อ่านเพี้ยนทั้งบรรทัดได้ ถ้ายังมีบางคำอ่านพอถูก
    (เช่น "$ometWiw fishv" -> มี "fishv"~"fishy" -> Something Fishy).
    ratio = เกณฑ์ความคล้ายของคำ (ต่ำลง = หลวมขึ้น) ใช้ตอน region-anchored ได้ปลอดภัย."""
    otoks = _tokens(key)
    if not otoks:
        return None
    best: Rumour | None = None
    best_score = 0.0
    for rtoks, rumour in _RUMOUR_TOKENS:
        score = 0.0
        strong = 0
        for ot in otoks:
            top = max((_ratio(ot, rt) for rt in rtoks), default=0.0)
            if top >= ratio:
                score += top
                strong += 1
        if strong >= 1 and score > best_score:
            best_score = score
            best = rumour
    return best


def lookup(raw_text: str, token_ratio: float = _TOKEN_RATIO) -> Rumour | None:
    """จับชื่อข่าวลือจากข้อความ OCR -> Rumour (None ถ้าไม่ใกล้พอ).
    ลำดับ: exact -> วลีย่อย (มี "The" นำหน้า/คำเกินก็เจอ) -> fuzzy -> ทีละคำเด่น.
    token_ratio ต่ำลง = จับคำเด่นหลวมขึ้น (find_in_lines ส่งค่าต่ำมาได้ เพราะ region-anchored)."""
    key = _key(raw_text)
    if not key:
        return None
    hit = _INDEX.get(key)
    if hit is not None:
        return hit

    # วลีย่อย: คีย์ข่าวลือเป็นส่วนหนึ่งของข้อความ OCR หรือกลับกัน (จัดการ "The last to fall"
    # ที่มีคำเกิน, หรือ OCR อ่านขาดหาย). เลือกคีย์ที่ "ยาวสุด" = เจาะจงสุด
    best_contain: Rumour | None = None
    best_len = _MIN_CONTAIN - 1
    for cand_key, rumour in _INDEX.items():
        if len(cand_key) < _MIN_CONTAIN:
            continue
        if (cand_key in key or key in cand_key) and len(cand_key) > best_len:
            best_len = len(cand_key)
            best_contain = rumour
    if best_contain is not None:
        return best_contain

    # fuzzy ทั้งบรรทัด — เผื่อ OCR อ่านเพี้ยนเล็กน้อย
    best: Rumour | None = None
    best_score = _FUZZY_THRESHOLD
    for cand_key, rumour in _INDEX.items():
        score = _ratio(key, cand_key)
        if score >= best_score:
            best_score = score
            best = rumour
    if best is not None:
        return best

    # ทีละคำเด่น — ด่านสุดท้าย เผื่อ OCR อ่านมั่วทั้งบรรทัดแต่ยังมีบางคำพอถูก
    return _token_match(key, token_ratio)


def find_in_lines(texts: list[str]) -> list[tuple[int, Rumour]]:
    """รับข้อความ OCR ทุกบรรทัด (เรียงบนลงล่าง) -> [(index, Rumour)] เฉพาะข่าวลือ.

    จับเฉพาะบรรทัดที่อยู่ "ระหว่างหัวข้อ Island Rumours กับ Requires/Consumes" —
    เพราะข่าวลือในหน้า Logbook อยู่ช่วงนั้นเป๊ะเสมอ. ได้ 2 ผลพลอยได้สำคัญ:
      1) ตัดหัวหน้าต่าง "Uncharted Waters" (อยู่เหนือหัวข้อ) ออก ไม่ไปชน "Reflective Waters"
      2) ตอนเช็คราคาปกติ (ไม่มีหัวข้อนี้บนจอ) จะคืน [] — ไม่มี false positive เลย
    ถ้า OCR อ่านหัวข้อไม่เจอ ก็คืน [] (ถือว่าไม่ได้อยู่หน้า Logbook)."""
    start: int | None = None
    end: int | None = None
    for i, text in enumerate(texts):
        n = normalize(text)
        if start is None and "rumours" in n:
            start = i + 1
        elif start is not None and ("requires" in n or "consumes" in n):
            end = i
            break
    if start is None:
        return []
    out: list[tuple[int, Rumour]] = []
    seen: set[str] = set()
    for i in range(start, end if end is not None else len(texts)):
        hit = lookup(texts[i], token_ratio=_TOKEN_RATIO_REGION)
        if hit is not None and hit.name not in seen:
            seen.add(hit.name)
            out.append((i, hit))
    return out
