"""Entry point สำหรับรัน/►build เป็น .exe — import แบบ package ให้ relative import ทำงาน.

รันจากซอร์ส:  py run.py        (เทียบเท่า py -m poe_price.app)
build .exe:    ใช้ build.bat
"""

from poe_price.app import main

if __name__ == "__main__":
    raise SystemExit(main())
