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
| `mk_tagnote.py` | สร้าง `agg.tagnote` (ตาราง "แชทที่ติดแท็ก / ติดโน้ต") จากชีทรายปี + **bundle ดิบ** |
| `mk_tnfu.py` | สร้าง `agg.tnfu` (Follow up · ติดแท็ก / ใส่โน้ต ให้ครบ) **จากศูนย์** — ต้องมี bundle ครบทั้งปี ใช้ครั้งแรกเท่านั้น |
| `tn_update.py` | อัปเดต `agg.tnfu` **ต่อจากของเดิม** ใช้ทุกรอบ · `--todo src out.json` = รหัสห้องที่ต้องเช็กโน้ต (ส่งให้ `notesFor`) |
| `tn_auto.py` | รอบเช้า (GitHub Actions) เรียกเอง: ใช้ไฟล์ดิบ LINE บน Drive ที่ใหม่กว่ารอบเดิม → `tn_update.py` |
| `tn_apply.py` | ขึ้น `agg.tnfu` ใหม่โดยเข้ารหัสเฉพาะ `data/agg.json` ด้วย salt เดิม (รอบที่ดึงแท็ก/โน้ตอย่างเดียว) |

## ขั้นตอนหนึ่งรอบ (สำหรับ Claude)
1. **เช็กเครื่อง** — เปิด `https://chat.line.biz/U38b62d24ef14a84a048cd6633fc15d21` ใน browser pane ถ้า URL เป็น account.line.biz/login = session หลุด → แจ้งเจ้าของให้ล็อกอิน แล้วหยุด (ห้ามกรอกรหัสผ่านเอง) · ถ้ามีตัวดึงรันอยู่ (`window.LINEPULL?.running`) ห้ามเริ่มซ้อน
2. **ดึง** — (ไม่บังคับ) ถ้าถอดข้อมูลได้: unpack ใน sandbox แล้ว `python3 tools/line/tn_update.py --todo src todo.json` เอา `notesFor` จาก todo.json · วางเนื้อหา `puller.js` แล้ว `LINEPULL.start({from:'YYYY-MM-01', to:'<วันที่ 1 เดือนถัดไป>', db:'lp_YYYY_MM_<วันนี้>', notesFor:[...]})` (db ใหม่ทุกรอบ · notesFor = เช็กโน้ตห้องที่ยังค้างในรายการแท็ก/โน้ต แม้ไม่ได้คุยเดือนนี้) · ถ้าเป็นจันทร์แรกของเดือน ดึงเดือนที่แล้วให้จบก่อน แล้วค่อยดึงเดือนปัจจุบัน — ห้ามรันพร้อมกัน · โพลทุก ~10 นาที · ~260 หน้า + ~2–3 requests/ห้อง, ~1,100–1,300 requests/ชม.
3. **ส่งออก** — `await LINEPULL.bundle()` → แจ้งเจ้าของให้อัป `line_YYYY-MM_raw.json.gz` จาก Downloads ขึ้น Google Drive → โพล Drive หาไฟล์ชื่อนั้น
4. **Build แดชบอร์ด** (Composio workbench, clone ลง /tmp เท่านั้น): clone repo · `admin_secret.txt` จาก Drive โฟลเดอร์ `17elxhEhju_gUi8P7tR-iu68QMLKomXiD` → `secret.txt` · `python3 tools/line/line_month.py <bundle> out` · `sh tools/line/build_month.sh out/line_YYYY-MM.json.gz <bundle ดิบทุกไฟล์ของรอบนี้ เก่า→ใหม่>` (**ต้องใส่ bundle ดิบ** ไม่งั้นรายการแท็ก/โน้ตไม่อัปเดต — ค้างที่ 22 ก.ย. มาแล้วครั้งหนึ่ง) · เทียบ agg ก่อน/หลัง (FB/IG ต้องไม่เปลี่ยน ยกเว้นผลจากกฎสลิปซ้ำ) · `node tools/line/smoke.js pages secret.txt` ต้องผ่าน
5. **Push** — `gh_token.txt` จาก Drive โฟลเดอร์เดียวกัน · เช็กว่า origin HEAD ไม่ขยับระหว่างทำ · คัดลอก `pages/index.html`, `pages/manifest.json`, `pages/data/*` ขึ้น root แล้ว commit + push · ลบ token ทันที · เช็ก manifest ที่หน้าเว็บจริงมีเดือนนั้น
6. **ชีท** — `write_month(run_composio_tool, SID, S)` แล้ว `rebuild_overview(run_composio_tool, SID, agg, {month: S['reg']}, '<บรรทัดที่มา>', partial='<ถ้าเดือนยังไม่จบ>')` · SID = `1TPJVVmIcfRxjXvQNHU2IlvMDDL6Oc8TsXn1tQMIbaOY` · เขียนได้ไม่เกิน 60 ครั้ง/นาที (สคริปต์ retry ให้)
7. **เก็บกวาด** — ลบ /tmp ที่มีข้อมูลถอดรหัสและ token · บอกเจ้าของว่าลบไฟล์บน Drive/Downloads ได้

## รายการ "ติดแท็ก / ใส่โน้ต ให้ครบ" อัปเดตยังไง (6 ต.ค. 2026)
- **อัตโนมัติ:** รอบเช้าใน GitHub Actions (`tools/auto/refresh.py` → `fetch_line_raw` + `tools/line/tn_auto.py`) หาไฟล์ `line_*_raw.json.gz`
  ที่แก้ไขใน 21 วันล่าสุดบน Drive ใช้เฉพาะไฟล์ที่ดึงหลังรอบที่อยู่ในแดชบอร์ด แล้วอัปเดต `agg.tnfu` ให้เอง — แค่อัปไฟล์ดิบขึ้น Drive ก็พอ
  ไม่ต้องให้ใครถือรหัสผ่าน (Actions ใช้ secret ของ repo) · log พิมพ์แต่ตัวเลข
- ไฟล์จากตัวดึงรุ่นใหม่ (มี `tagall`) = แท็กล่าสุด**ทุกห้อง** · ไฟล์รุ่นเก่า = เฉพาะห้องที่คุยในช่วงที่ดึง
- โน้ต: เช็กใหม่เฉพาะห้องที่อยู่ในไฟล์ (`checked`) ห้องอื่นใช้สถานะเดิม · ถ้าอยากให้เช็กโน้ตห้องเก่าที่ค้างด้วย ส่ง `notesFor` ตอนดึง
  (`tn_update.py --todo src todo.json` ต้องถอดข้อมูลก่อน) หรือดึงแบบ `mode:'tn'` ที่ `from` ย้อนไปต้นปี (เช็กโน้ตทุกห้องของปี ~4 ชม.)
- ทำมือ (ถ้าต้องการขึ้นทันทีไม่รอรอบเช้า): unpack → `tn_update.py src <ไฟล์> --dry` ดูรายงาน → `tn_update.py src <ไฟล์>` → `tn_apply.py`
  (เปลี่ยนแค่ data/agg.json) → `node tools/line/smoke.js . secret.txt` → commit + push
- รายงาน `bump.note_new_act_after / note_new` บอกว่า LINE ขยับเวลาห้องตอนเขียนโน้ตไหม — ถ้าขยับเกือบทุกห้อง รอบรายเดือนไม่ต้องส่ง notesFor

## กฎที่ห้ามเปลี่ยนโดยไม่ถาม
- ห้องแชท = มีข้อความอย่างน้อย 1 ข้อความในเดือน (follow/unfollow อย่างเดียวไม่นับ) · เฉพาะแชท 1:1
- ปิดการขาย = สลิป "สถานะ: ตรวจสอบสลิปสำเร็จ" / ผู้รับ บจก. ไบโอปาล์ม เอ็ดดูเคชั่น · เลขอ้างอิงเดียวกันนับครั้งเดียว (ตามลำดับเวลา ข้ามช่องทาง)
- ยอดลงทะเบียนมาจากโน้ตที่มีรหัส G และสร้างในเดือนนั้น (G000 = เทป) — แท็ก Q-สมัครแล้ว ติดที่ห้อง ไม่ใช่ยอดรายเดือน
- ตาราง "แชทที่ติดแท็ก / ติดโน้ต" (`agg.tagnote`) — วันที่ของโน้ต **ต้องอ่านจาก bundle ดิบเท่านั้น** ห้ามอ่านจากชีท
  เพราะชีทรายปีเก็บเฉพาะโน้ตที่เขียนในปีนั้น โน้ตปี 2025 (1,345 ใบ / 879 ห้อง) ไม่อยู่ในชีท
  ถ้าใช้ชีทเป็นแหล่งวันที่ ม.ค. 2026 จะเหลือห้องที่ "มีโน้ต" ใบเดียว (ผิด — ที่ถูกคือ 330 ห้อง)
  `mk_tagnote.py` เช็กให้เองว่าทุกห้องในชีทมี bundle ครอบคลุม ถ้าขาดจะหยุดและบอกว่าต้องดึงโน้ตห้องไหนเพิ่ม
