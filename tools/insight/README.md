# tools/insight — Insight แชท (Biopalm)

`run.py` อ่านแชท FB / IG / LINE ทั้งปีจากข้อมูลแดชบอร์ดใน repo นี้ (`data/*.json` ถอดรหัสในเครื่อง runner ด้วย secret `ADMIN_SECRET` เดิม —
ป้ายคน/บอทถูกแก้ด้วยป้าย Meta แล้ว) + โน้ตลงทะเบียน LINE (รหัสคอร์ส G) จากชีต **Biopalm LINE Chat Log — 2026** ผ่าน Composio ตัวเดิม
แล้ววิเคราะห์ในเครื่อง runner ชั่วคราว จากนั้นเขียนผลสรุปลง vault private `biopalm-insight` ที่ `.vault/insight/`

ทำไมไม่อ่านแชทจากชีต: คำตอบผ่าน Composio MCP ถูกจำกัดขนาด อ่านข้อความทั้งปี (~640,000 แถว) ต้องยิงหลายพันครั้ง เกินเวลา 2 ชม. (ลองแล้ว 27 ต.ค. 2026)

- รันโดย `.github/workflows/obsidian-insight.yml` (กด Run workflow เอง · ยังไม่ตั้งเวลา) — ไม่แตะงาน refresh-dashboard / obsidian-vault
- repo นี้ public: log พิมพ์แค่ชื่อขั้นและจำนวน · ข้อความ error ดิบ/รายละเอียดอยู่ใน `.vault/insight/run_log.txt` (private) เท่านั้น
- ลำดับ: mk_rules → build_db_hub → ex_cards → purchases → features → roles → an1 → an2 → an3 → summarize (→ samples เฉพาะตอนกด Run workflow แล้วติ๊ก samples)
- กติกาที่ใช้ร่วมกับ admin-hub: `stage_rules.py` (สรุปจ่าย / แนบตัวอย่าง), สลิป = "ตรวจสอบสลิปสำเร็จ" หรือผู้รับ บจก. ไบโอปาล์ม,
  ปุ่ม/คำทักทายจาก `build_pay.py` + `build_v4.py`, กฎคน/บอทของ FB ม.ค.–ส.ค. ใช้วิธีเดียวกับ `fix_roles.py` (เทียบข้อความเดียวกันใน ก.ย.–ต.ค. + เวลา 2 นาที)
- `catalog.json` = รหัสคอร์ส G → ชื่อคอร์ส/ระดับชั้น จาก New_Control Sheet (แท็บ Course + Closed Course)
- `build_db.py` / `relabel.py` = ทางเดิมที่อ่านจากชีต (เก็บไว้สำรอง ไม่ได้อยู่ในลำดับ)
