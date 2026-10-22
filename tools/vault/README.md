# tools/vault — Obsidian vault (Biopalm Insight)

`build_vault.py` อ่านชีต Meta Ads + FB/LINE/IG chat log (อ่านอย่างเดียว) แล้ว commit โน้ต Obsidian ลง repo **private** `biopalm-education/biopalm-insight`

- รันโดย `.github/workflows/obsidian-vault.yml` ต่อจาก refresh-dashboard ทุกเช้า · กด Run workflow เองได้ (ใส่เดือน เช่น `2026-09`)
- ใช้ Composio ตัวเดิมผ่าน `tools/meta_ads/composio_shim.py` ทั้งอ่านชีตและเขียน GitHub — ไม่มี secret ใหม่
- repo นี้ public: สคริปต์พิมพ์แค่จำนวน ห้ามเพิ่ม print ที่มีชื่อ/ข้อความลูกค้า หรือคำตอบดิบจาก GitHub
- โฟลเดอร์ที่สคริปต์เขียนทับใน vault: `Ads/` `Monthly/` `Sources/` `Chats/FB/<เดือนที่ประมวลผล>/` `.vault/` `05 สถานะระบบ.md` (เก็บโน้ตแชท 3 เดือนล่าสุด)
- ไฟล์ที่สร้างครั้งแรกถ้ายังไม่มี แล้วไม่แตะอีก: `Config/` `Topics/` `Templates/` `Bases/` `บันทึกของฉัน/`
- sentiment: คำสำคัญจาก `Config/คำ sentiment.md` + หัวข้อจาก `keywords` ใน `Topics/*.md` ของ vault (ผู้ใช้แก้ใน Obsidian ได้)
