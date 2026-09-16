# admin-hub — Admin Performance

โคลนจาก [chat-hub](https://biopalm-education.github.io/chat-hub/) (commit a6241e1, 16 ก.ย. 2026) สำหรับทีมแอดมินโดยเฉพาะ · ใช้รหัสผ่านแยกจากตัวหลัก

Dashboard สรุปแชท Instagram / Facebook ของ BioPalm — เปิดที่
<https://biopalm-education.github.io/admin-hub/> (ต้องใส่ชื่อผู้ใช้และรหัสผ่านของทีม)

## ไฟล์ในรีโปนี้

| ไฟล์ | คืออะไร |
|---|---|
| `index.html` | โค้ดทั้งหมดของ dashboard — **ไม่มีข้อมูลลูกค้าอยู่ในไฟล์นี้เลย** |
| `manifest.json` | salt + จำนวนรอบ PBKDF2 + ตัวตรวจรหัสผ่าน + รายชื่อไฟล์ข้อมูล |
| `data/agg.json` | ตัวเลขสรุปทุกเดือน (โหลดทันทีหลังใส่รหัส) |
| `data/ig-all.json` | บทสนทนา Instagram ทุกเดือน (โหลดตอนกดดู Instagram) |
| `data/fb-YYYY-MM.json` | บทสนทนา Facebook รายเดือน (โหลดตอนกดดูเดือนนั้น) |
| `app.html` | ต้นฉบับของ `index.html` — แก้โค้ด dashboard ที่ไฟล์นี้ |
| `build.py` | เข้ารหัส `src/*.json` เป็น `data/*` + `manifest.json` แล้วคัดลอก `app.html` เป็น `index.html` |
| `deploy.sh` | build แล้ว push ขึ้น GitHub Pages (อ่าน token จาก `gh_token.txt` ที่ไม่ได้อยู่ในรีโป) |
| `extract.py` | สคริปต์ครั้งเดียว ใช้ตอนแตกข้อมูลออกจาก HTML ก้อนเดิม |

ทุกไฟล์ใน `data/` และตัวตรวจใน `manifest.json` เข้ารหัส AES-256-GCM ด้วยกุญแจที่ได้จาก
PBKDF2-SHA256 250,000 รอบ จาก `ชื่อผู้ใช้:รหัสผ่าน` การถอดรหัสเกิดในเบราว์เซอร์เท่านั้น
รหัสผ่านไม่ถูกส่งออกไปไหน

## เพิ่มข้อมูลเดือนใหม่

ข้อมูลต้นทาง (`src/`) รหัสผ่าน (`secret.txt`) และ token (`gh_token.txt`) ไม่ได้อยู่ในรีโปนี้ —
เก็บไว้ในเครื่องที่ `Downloads\biopalm_work\hub\` ขั้นตอนคือ

1. วาง `src/fb_YYYY-MM.json` ของเดือนใหม่ และอัปเดต `src/agg.json`
2. `./deploy.sh "ข้อความ commit"` — build ใหม่แล้ว push ขึ้น GitHub Pages

`index.html` จะเปลี่ยนก็ต่อเมื่อแก้โค้ดใน `app.html` เท่านั้น การเพิ่มเดือนไม่ต้องแตะ HTML
