"""poe.ninja (PoE2) exchange API client.

ยิงไปที่ exchange/current/overview ทีละ "type" แล้ว parse JSON ออกมาเป็น
dict ของ {key -> PriceEntry}. ใช้ urllib จาก standard library ล้วน ไม่มี dep.

รูปร่าง response (exchange/current/overview):
  items[]      -> { id, name }            ใช้ map id -> ชื่อแสดงผล
  lines[]      -> { id, primaryValue }    ราคาในสกุล primary ของลีก
  core.primary -> "divine" | "exalted"    primaryValue คิดเป็นสกุลไหน
  core.rates   -> { exalted, divine, ... } กี่หน่วยของสกุลนั้น = 1 primary
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .models import PriceEntry
from .normalizer import normalize

BASE_URL = "https://poe.ninja/poe2/api/economy/exchange/current/overview"

# หมวด "GENERAL" ของ poe.ninja ที่ยิง exchange API ได้จริง (ยืนยันกับลีก Runes of Aldur).
# ครอบคลุมของที่โผล่ในเกือบทุก panel รวม alloy (อยู่ในหมวด Verisium). ต้นฉบับใช้แค่ 5
# หมวด (Currency/Runes/Expedition/Verisium/UncutGems) เพราะทำเฉพาะ panel Verisium Remnant —
# เราดึงกว้างกว่าเพื่อตีราคาของทั่วไปได้. ปรับชุดได้ผ่าน PriceRepository(types=...).
EXCHANGE_TYPES: tuple[str, ...] = (
    "Currency", "Fragments", "UncutGems", "LineageSupportGems", "Essences",
    "SoulCores", "Idols", "Runes", "Expedition", "Verisium",
)

# หมวดที่เห็นบนเว็บแต่ exchange endpoint นี้ "ไม่ส่งข้อมูล" (คืน 0) — ใช้ API คนละ endpoint:
#   AbyssalBones, Omens, LiquidEmotions, BreachCatalyst  (fungible แต่อยู่ overview อื่น)
#   Unique* (weapons/armours/.../relics), UniqueTablets, PrecursorTablets  (item overview แยก)
# จงใจไม่ดึง: ยิงเปล่าเสีย bandwidth + ของ unique ตีราคาด้วยชื่ออย่างเดียวไม่แม่น (หลาย variant)
# + ชื่อยาวเสี่ยง fuzzy match ผิด. ถ้าจะรองรับต้องเขียน parser สำหรับ item-overview แยก.

# poe.ninja กรอง bot ด้วย User-Agent/Referer — เลียนแบบ browser ปกติ.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)


class PriceFetchError(RuntimeError):
    """ดึงราคาของ type หนึ่งไม่สำเร็จ (HTTP error / network / JSON เพี้ยน)."""


def build_request(league: str, exchange_type: str) -> urllib.request.Request:
    slug = league.replace(" ", "").lower()
    type_slug = exchange_type.lower()
    query = urllib.parse.urlencode({"league": league, "type": exchange_type})
    url = f"{BASE_URL}?{query}"
    headers = {
        "User-Agent": _USER_AGENT,
        "Referer": f"https://poe.ninja/poe2/economy/{slug}/{type_slug}",
        "Accept": "application/json",
    }
    return urllib.request.Request(url, headers=headers)


def fetch_type(league: str, exchange_type: str, timeout: float = 30.0) -> dict[str, PriceEntry]:
    """ดึงและ parse ราคา 1 หมวด. ถ้า fail จะ raise PriceFetchError."""
    req = build_request(league, exchange_type)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise PriceFetchError(f"{exchange_type}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PriceFetchError(f"{exchange_type}: {exc}") from exc
    return parse_response(raw)


def parse_response(raw: str) -> dict[str, PriceEntry]:
    """แปลง JSON string -> {key -> PriceEntry}. แยกออกมาเป็นฟังก์ชันบริสุทธิ์
    เพื่อทดสอบได้แบบ offline โดยไม่ต้องยิงเน็ต."""
    result: dict[str, PriceEntry] = {}
    obj = json.loads(raw)

    # id -> ชื่อแสดงผล
    name_map: dict[str, str] = {}
    for item in obj.get("items") or []:
        item_id = item.get("id")
        name = item.get("name")
        if item_id is not None and name is not None:
            name_map[item_id] = name

    # rates[x] = กี่ x เท่ากับ 1 หน่วยของ primary. ถ้า primary คือ divine/exalted เอง
    # rate ของมันคือ 1 โดยปริยาย (และมักไม่อยู่ใน rates).
    core = obj.get("core") or {}
    primary = core.get("primary") or "divine"
    rates = core.get("rates") or {}
    divine_per_primary = 1.0 if primary == "divine" else float(rates.get("divine") or 0.0)
    exalted_per_primary = 1.0 if primary == "exalted" else float(rates.get("exalted") or 1.0)
    chaos_per_primary = 1.0 if primary == "chaos" else float(rates.get("chaos") or 0.0)

    for line in obj.get("lines") or []:
        line_id = line.get("id")
        if line_id is None or line_id not in name_map:
            continue
        key = normalize(name_map[line_id])
        if not key:
            continue
        primary_value = line.get("primaryValue")
        if primary_value is None:
            # poe.ninja รู้จักไอเทมแต่ยังไม่มีข้อมูลซื้อขาย — เก็บไว้แต่ mark ว่าไม่มีข้อมูล.
            result[key] = PriceEntry(0.0, 0.0, has_market_data=False)
            continue
        primary_value = float(primary_value)
        divine_value = primary_value * divine_per_primary
        exalted_value = round(primary_value * exalted_per_primary, 1)
        chaos_value = round(primary_value * chaos_per_primary, 1)
        result[key] = PriceEntry(divine_value, exalted_value, chaos_value)

    return result
