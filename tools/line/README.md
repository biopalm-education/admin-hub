# LINE OA → admin-hub + ชีท "Biopalm LINE Chat Log — 2026"

ชุดเครื่องมืออัปเดตข้อมูล LINE OA (bot Biopalm `U38b62d24ef14a84a048cd6633fc15d21` เท่านั้น — ห้ามแตะ OA อื่นในบัญชีเดียวกัน)
ใช้ทั้งรอบรายสัปดาห์ (เดือนปัจจุบันถึงเมื่อวาน) และรอบปิดเดือน

## ทำไมต้องทำแบบนี้
- LINE ไม่มี API ดึงแชทย้อนหลัง → ดึงผ่าน API ภายในของ chat.line.biz จาก **browser pane ในแอป Claude บนเครื่องที่ล็อกอิน LINE Business ID ไว้**
- ไฟล์ที่ดึงได้ส่งเข้า Drive เองไม่ได้ → **ต้องให้คนอัปไฟล์ขึ้น Drive 1 ครั้งต่อรอบ**
- LINE เรียงห้องตาม `updatedAt` ซึ่งบางห้องไม่ขยับทั้งที่ยังคุยอยู่ → **ต้องไล่รายชื่อห้องทั้งบัญชีทุกรอบ** (~260 หน้า) ห้ามหยุดที่วันที่ 1

## ไฟล์
| ไฟล์ | หน้าที่ |
|---|---|
| `puller.js` | วางใน browser pane (javascript_tool) → `LINEPULL.start({from,to,db})` · `LINEPULL.status()` · `LINEPULL.bundle()` ดาวน์โหลด `line_YYYY-MM_raw.json.gz` |
| `convert.py` | แปลงเหตุการณ์ดิบเป็นห้องแชท — ทดสอบแล้วตรงกับข้อมูล พ.ค./เม.ย. ที่ขึ้นแดชบอร์ดทุกห้องทุกฟิลด์ |
| `line_month.py` | bundle → `out/line_YYYY-MM.json.gz` (ให้ mk_line.py) + `out/sheet_YYYY-MM.json` (แถวชีท + ยอดลงทะเบียนจากโน้ต) |
| `build_month.sh` | unpack → mk_line → keep_legacy → build_v4 → build_v5 → post_v5_speed → build (ลำดับห้ามสลับ) |
| `keep_legacy.py` | เก็บคีย์ v/unansQ/adminScore เดิมใน agg.line ที่ mk_line ลบทิ้ง |
| `smoke.js` | ทดสอบหน้าเว็บที่ build แล้วใน jsdom ทุกช่องทาง × ทุกเดือน |
| `sheet_month.py` | เขียนเดือนลงชีท (แทนที่ของเดิมถ้ามี) + ตรวจจำนวนแถว |
| `overview.py` | สร้างแท็บ "สรุปภาพรวม (รายเดือน)" ใหม่จาก agg ทุกเดือน |

## ขั้นตอนหนึ่งรอบ (สำหรับ Claude)
1. **เช็กเครื่อง** — เปิด `https://chat.line.biz/U38b62d24ef14a84a048cd6633fc15d21` ใน browser pane ถ้า URL เป็น account.line.biz/login = session หลุด → แจ้งเจ้าของให้ล็อกอิน แล้วหยุด (ห้ามกรอกรหัสผ่านเอง) · ถ้ามีตัวดึงรันอยู่ (`window.LINEPULL?.running`) ห้ามเริ่มซ้อน
2. **ดึง** — วางเนื้อหา `puller.js` แล้ว `LINEPULL.start({from:'YYYY-MM-01', to:'<วันที่ 1 เดือนถัดไป>', db:'lp_YYYY_MM_<วันนี้>'})` (db ใหม่ทุกรอบ) · ถ้าเป็นจันทร์แรกของเดือน ดึงเดือนที่แล้วให้จบก่อน แล้วค่อยดึงเดือนปัจจุบัน — ห้ามรันพร้อมกัน · โพลทุก ~10 นาที · ~260 หน้า + ~2–3 requests/ห้อง, ~1,100–1,300 requests/ชม.
3. **ส่งออก** — `await LINEPULL.bundle()` → แจ้งเจ้าของให้อัป `line_YYYY-MM_raw.json.gz` จาก Downloads ขึ้น Google Drive → โพล Drive หาไฟล์ชื่อนั้น
4. **Build แดชบอร์ด** (Composio workbench, clone ลง /tmp เท่านั้น): clone repo · `admin_secret.txt` จาก Drive โฟลเดอร์ `17elxhEhju_gUi8P7tR-iu68QMLKomXiD` → `secret.txt` · `python3 tools/line/line_month.py <bundle> out` · `sh tools/line/build_month.sh out/line_YYYY-MM.json.gz` · เทียบ agg ก่อน/หลัง (FB/IG ต้องไม่เปลี่ยน ยกเว้นผลจากกฎสลิปซ้ำ) · `node tools/line/smoke.js pages secret.txt` ต้องผ่าน
5. **Push** — `gh_token.txt` จาก Drive โฟลเดอร์เดียวกัน · เช็กว่า origin HEAD ไม่ขยับระหว่างทำ · คัดลอก `pages/index.html`, `pages/manifest.json`, `pages/data/*` ขึ้น root แล้ว commit + push · ลบ token ทันที · เช็ก manifest ที่หน้าเว็บจริงมีเดือนนั้น
6. **ชีท** — `write_month(run_composio_tool, SID, S)` แล้ว `rebuild_overview(run_composio_tool, SID, agg, {month: S['reg']}, '<บรรทัดที่มา>', partial='<ถ้าเดือนยังไม่จบ>')` · SID = `1TPJVVmIcfRxjXvQNHU2IlvMDDL6Oc8TsXn1tQMIbaOY` · เขียนได้ไม่เกิน 60 ครั้ง/นาที (สคริปต์ retry ให้)
7. **เก็บกวาด** — ลบ /tmp ที่มีข้อมูลถอดรหัสและ token · บอกเจ้าของว่าลบไฟล์บน Drive/Downloads ได้

## กฎที่ห้ามเปลี่ยนโดยไม่ถาม
- ห้องแชท = มีข้อความอย่างน้อย 1 ข้อความในเดือน (follow/unfollow อย่างเดียวไม่นับ) · เฉพาะแชท 1:1
- ปิดการขาย = สลิป "สถานะ: ตรวจสอบสลิปสำเร็จ" / ผู้รับ บจก. ไบโอปาล์ม เอ็ดดูเคชั่น · เลขอ้างอิงเดียวกันนับครั้งเดียว (ตามลำดับเวลา ข้ามช่องทาง)
- ยอดลงทะเบียนมาจากโน้ตที่มีรหัส G และสร้างในเดือนนั้น (G000 = เทป) — แท็ก Q-สมัครแล้ว ติดที่ห้อง ไม่ใช่ยอดรายเดือน
