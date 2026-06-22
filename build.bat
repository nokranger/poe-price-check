@echo off
REM ===== Build PoE Price Helper เป็นไฟล์ .exe เดียว (portable) =====
REM ต้องมี Python + ติดตั้ง requirements แล้ว. รันไฟล์นี้ดับเบิลคลิกได้เลย.

echo [1/2] ตรวจ/ติดตั้ง PyInstaller ...
py -m pip install --quiet pyinstaller

echo [2/2] กำลัง build (ใช้เวลาสักครู่) ...
py -m PyInstaller --noconfirm --onefile --windowed --name "PoE Price Check" ^
  --add-data "img;img" ^
  --collect-all winrt ^
  --collect-submodules poe_price ^
  run.py

echo.
echo เสร็จแล้ว! ไฟล์อยู่ที่  "dist\PoE Price Check.exe"
echo (แจกไฟล์เดียวนี้ได้เลย ดับเบิลคลิกเปิดใช้งาน ไม่มีหน้าต่าง cmd)
pause
