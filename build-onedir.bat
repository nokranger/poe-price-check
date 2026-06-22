@echo off
REM ===== Build แบบ onedir + zip (โดน antivirus เตือนน้อยกว่า --onefile มาก) =====
REM ได้ผลลัพธ์เป็น dist\PoE-Price-Check.zip -> แจก zip นี้
REM ผู้ใช้แตก zip แล้วเปิด "PoE Price Check.exe" ข้างในโฟลเดอร์

echo [1/3] ตรวจ/ติดตั้ง PyInstaller ...
py -m pip install --quiet pyinstaller

echo [2/3] กำลัง build (onedir) ...
py -m PyInstaller --noconfirm --onedir --windowed --name "PoE Price Check" ^
  --add-data "img;img" ^
  --collect-all winrt ^
  --collect-submodules poe_price ^
  run.py

echo [3/3] zip โฟลเดอร์ + สร้าง SHA256 ...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\PoE Price Check' -DestinationPath 'dist\PoE-Price-Check.zip' -Force"
powershell -NoProfile -Command "(Get-FileHash 'dist\PoE-Price-Check.zip' -Algorithm SHA256).Hash" > "dist\PoE-Price-Check.zip.sha256.txt"

echo.
echo เสร็จแล้ว!
echo   ไฟล์แจก : dist\PoE-Price-Check.zip   (แตกแล้วเปิด exe ข้างใน)
echo   SHA256  : dist\PoE-Price-Check.zip.sha256.txt
echo (onedir โดน antivirus เตือนน้อยกว่า onefile)
pause
