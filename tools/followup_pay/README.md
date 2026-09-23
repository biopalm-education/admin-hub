# Follow up · ตามโอนเงิน (preview 23 ก.ย. 2026)

หน้า "Follow up" ใน admin-hub/preview/ มี 2 รายการ สลับด้วยปุ่มใหญ่ด้านบน
- 💬 ตอบแชทค้าง · Auto reply (รายการเดิม) — เปลี่ยน checkbox 2 อันเป็นตัวเลือกกลุ่มแบบเลือกทีละกลุ่ม
  (ไม่เคยมีแอดมินคุย · เคยคุยแล้ว ถามรอบใหม่ · รวมสองกลุ่ม · ไม่ต้องตาม) และตัวเลขในกล่อง "อ่านทั้งห้องแชท" กดแล้วเปิดรายชื่อได้
- 💸 ตามโอนเงิน · ส่งราคาแล้วยังไม่โอน (ใหม่) — build_pay.py → key "pay" ใน followup.json

ไฟล์ในโฟลเดอร์นี้ = ของที่ต้องย้ายไป root ตอน deploy
- build_pay.py  → วางที่ root (build_fu.py เรียกเองตอนท้าย)
- build_fu.py   → แทน root/build_fu.py (เรียก build_pay + แก้วันสิ้นสุด LINE = ข้อความล่าสุด ไม่ใช่สิ้นเดือน)
- app.html      → แทน root/app.html และ index.html
tools/auto/refresh.py ไม่ต้องแก้ เพราะ build_fu.py เรียก build_pay.py เอง

Deploy: copy 3 ไฟล์ขึ้น root → unpack.py → build_fu.py → build.py (root) → push
หรือ copy preview/index.html + preview/manifest.json + preview/data/* ไป root (ข้อมูลชุด 23 ก.ย. 05:00) แล้ว copy 3 ไฟล์
