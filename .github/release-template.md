# PoE Price Check {TAG}

## 📖 วิธีใช้ (อ่านตรงนี้ก่อน!)

1. ตั้งเกมเป็น **Windowed / Borderless** (ห้าม Exclusive Fullscreen)
2. เปิดโปรแกรม รอมุมซ้ายบนขึ้น **"พร้อม! ได้ราคา…"**
3. ในเกมเปิดหน้าต่างของ/ค่าเงิน → กด **F9** ราคาโผล่ข้างของ

> • **F6** = สลับหน่วยเงิน (divine → exalted → chaos) • **F8** = ตั้งค่า + วิธีใช้ • **Ctrl+Alt+Q** = ปิดโปรแกรม

❓ **ราคาไม่ขึ้น?** เกมต้องเป็น Windowed/Borderless เท่านั้น · หรือกด **F8 → "ดึงราคาใหม่ตอนนี้"** แล้วกด F9 ใหม่

{WHATS_NEW}

---

## 📥 ตอนโหลด / ติดตั้ง / ใช้งาน จะเกิดอะไรขึ้นบ้าง

**ตอนโหลด**
- โหลด **`{ZIP}`** ด้านล่าง → แตก zip → เปิด **`PoE Price Check.exe`** ในโฟลเดอร์ที่แตกออกมา
- เบราว์เซอร์หรือ Windows SmartScreen อาจเตือน "Unknown publisher" → กด **More info → Run anyway**
- แอนตี้ไวรัสบางตัวอาจแฟลก — เป็น **false positive** ของโปรแกรม Python ที่แพ็กด้วย PyInstaller และยังไม่ได้เซ็นโค้ด (ตรวจสอบไฟล์เองได้ ดูหัวข้อ 🔍 ด้านล่าง)

**ตอนติดตั้ง**
- **ไม่มีตัวติดตั้ง** — แตก zip แล้วใช้ได้เลย ไม่ยุ่งกับ registry ไม่ต้องสิทธิ์ admin
- เปิดครั้งแรก โปรแกรมจะสร้างโฟลเดอร์ `%LOCALAPPDATA%\PoePriceHelper` ไว้เก็บไฟล์ตั้งค่า (`config.json`) และ log (`log.txt`) — แค่นั้น ไม่เขียนไฟล์ที่อื่น
- **อยากลบโปรแกรม:** ลบโฟลเดอร์ที่แตก zip + ลบ `%LOCALAPPDATA%\PoePriceHelper` = สะอาดหมดจด

**ตอนใช้งาน**
- ต่อเน็ตที่เดียวคือ **poe.ninja** (HTTPS) เพื่อดึงราคา — ราคารีเฟรชเองทุก 30 นาที
- อ่าน "ภาพหน้าจอ" อย่างเดียว (เหมือนกด print screen) — **ไม่**อ่าน/เขียนหน่วยความจำเกม **ไม่** inject **ไม่**กดปุ่มแทนผู้เล่น → อ่านรายละเอียดที่ [SECURITY.md](https://github.com/{REPO}/blob/{TAG}/SECURITY.md)

---

## 🔍 ตรวจสอบไฟล์ (สำหรับคนไม่ไว้ใจ .exe จากคนอื่น)

ไฟล์ zip นี้ **build อัตโนมัติบน GitHub Actions จากซอร์สโค้ดของ tag `{TAG}`** — ไม่ได้ build บนเครื่องส่วนตัวของผู้พัฒนา ดูทุกขั้นตอนได้ที่ [build log]({RUN_URL})

**พิสูจน์ว่าไฟล์มาจากซอร์สนี้จริง** (ต้องมี [GitHub CLI](https://cli.github.com)):

```
gh attestation verify "{ZIP}" --repo {REPO}
```

ถ้าไฟล์ถูกแก้แม้แต่ byte เดียวหลัง build คำสั่งนี้จะ fail ทันที

**SHA256:** `{SHA256}`

---

## 🛠️ build เองจากซอร์ส (ทุกขั้นตอน — สำหรับคนอยากชัวร์ 100%)

1. ลง **Python 3.13** จาก [python.org](https://www.python.org/downloads/) (ตอนติดตั้งติ๊ก **"Add python.exe to PATH"**)
2. โหลดซอร์สโค้ดของเวอร์ชันนี้: [Source code (zip)](https://github.com/{REPO}/archive/refs/tags/{TAG}.zip) แล้วแตก zip (หรือ `git clone` แล้ว `git checkout {TAG}`)
3. เปิด Command Prompt ในโฟลเดอร์โปรเจกต์ แล้วติดตั้ง dependency:
   ```
   py -m pip install -r requirements.txt
   ```
4. (จะลองรันจากซอร์สก่อนก็ได้ ไม่ต้อง build: `py run.py`)
5. ดับเบิลคลิก **`build-onedir.bat`** → รอสักครู่ → ได้ไฟล์ `dist\PoE-Price-Check.zip` เหมือนตัวแจกทุกอย่าง
   (หรือ `build.bat` = .exe ไฟล์เดียว พกง่ายกว่าแต่โดนแอนตี้ไวรัสเตือนมากกว่า)

---

ของฟรี 100% ไม่มีล็อกฟีเจอร์ ไม่มีโฆษณา — ถ้าชอบ [สมัครสมาชิกช่อง Nokranger บน YouTube](https://www.youtube.com/c/NokrangerChannel/join) เพื่อสนับสนุนได้ 🙏
