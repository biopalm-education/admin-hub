# อัปเดตอัตโนมัติ (Facebook + Instagram)

`refresh.py` ดึงข้อมูลเดือนที่ระบุใหม่ทั้งเดือน แล้ว build + push ขึ้น GitHub Pages
ใช้กฎการจัดหมวดเดียวกับ `tools/month-pull` ห้ามแก้กฎ ไม่งั้นตัวเลขข้ามเดือนจะเทียบกันไม่ได้

## วิธีรัน (ต้องรันใน Composio workbench เพราะ Instagram ต้องใช้ run_composio_tool)

```python
# วางไฟล์ credential ไว้ที่ /tmp ก่อน (ดึงจาก Google Drive)
#   /tmp/gh_token.txt      file id 1dd4lHDqui2WpgXHitfCKU1y7QWHgjlbz
#   /tmp/admin_secret.txt  file id 1VbL4kjtGfAUgEu4g5RaQaJ3OVLnDp5bU
import subprocess
subprocess.run(['bash','-lc','rm -rf /tmp/ahb && git clone -q --depth 1 https://github.com/biopalm-education/admin-hub.git /tmp/ahb'])
exec(open('/tmp/ahb/tools/auto/refresh.py').read())
run_refresh(['2026-09'])                 # รอบรายวัน = เดือนปัจจุบัน
run_refresh(['2026-08','2026-09'])       # รอบวันจันทร์ = เดือนก่อนหน้า + เดือนปัจจุบัน
```

`run_refresh` จะ clone repo ใหม่เองทุกครั้ง แล้ว unpack ข้อมูลที่ deploy อยู่จริง
ก่อนเขียนทับเฉพาะเดือนที่ระบุ จึงไม่ทับงานของ session อื่น

## ทำไมต้องดึงเดือนก่อนหน้าซ้ำทุกสัปดาห์

ปิดการขายจำนวนมากเกิดในเดือนถัดจากเดือนที่เริ่มคุย (มิ.ย. 2026: 61% ของยอดปิด
มาจากห้องที่เริ่มคุยเดือนก่อน) ถ้าต่อท้ายข้อมูลอย่างเดียว ยอดปิดของเดือนที่แล้ว
จะต่ำกว่าความจริงถาวร

## LINE OA ไม่รวมอยู่ในนี้

LINE ไม่มี API อ่านย้อนหลัง ต้องดึงจาก session ที่ล็อกอิน chat.line.biz ในเบราว์เซอร์
ใช้เวลา ~3 ชม./เดือน จึงยังเป็นงานแมนนวลเดือนละครั้ง
