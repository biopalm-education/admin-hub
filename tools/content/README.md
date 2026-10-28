# insight คอนเทนต์ออร์แกนิก FB / IG / TikTok / YouTube

`pull.py` ดึงทุกโพสต์ของเพจ Facebook, Instagram, TikTok และ YouTube ตั้งแต่ 1 ม.ค. 2026 (ปรับด้วย `SINCE`) พร้อมตัวเลขรายโพสต์ · ส่วน TikTok/YouTube อยู่ใน `video.py`

| ช่องทาง | ตัวเลข | ที่มา (Composio) |
|---|---|---|
| FB | ยอดดู (post_media_view) · คนดูไม่ซ้ำ · reaction · คอมเมนต์ · แชร์ | `facebook` |
| IG | ยอดดู · reach · ไลก์ · คอมเมนต์ · เซฟ · แชร์ · interaction รวม · เข้าโปรไฟล์ · ฟอลโลว์ใหม่ · Reel: เวลาดูเฉลี่ย / เวลาดูรวม / อัตราปัดทิ้ง | `instagram` |
| TikTok | ยอดดู · ไลก์ · คอมเมนต์ · แชร์ · ความยาว (คลิปสาธารณะ) + ผู้ติดตาม/ไลก์รวมของบัญชี | `tiktok` (แอป TikTok for Developers ของเราเอง) |
| YouTube | ยอดดู · ไลก์ · คอมเมนต์ · ความยาว · Shorts/วิดีโอยาว/ไลฟ์ (ข้อมูลสาธารณะของช่อง BIOPALM) + ซับ/ยอดดูรวมของช่อง | `youtube` |

ป้าย "ทำแอด" ต่อโพสต์ (จำนวนโฆษณา + ค่าแอดตั้งแต่ `SINCE`):
- FB/IG: Meta Ads — creative ของแต่ละโฆษณา (`effective_object_story_id` / `effective_instagram_media_id`)
- TikTok: `tiktok_ads` รายงานรายโฆษณา — `ad_name` ขึ้นต้นด้วยแคปชันคลิป จึงจับคู่ด้วยแคปชัน · มียอดดูจากแอด (`video_play_actions`)
- YouTube: `googleads` GAQL `FROM video` รายเดือน — ค่าแอด · TrueView views · อัตราดูถึง 25/50/75/100% ของผู้ชมแอด
- TikTok/YouTube มี "ยอดดูที่ไม่ใช่แอด (ประมาณ)" = ยอดดู − ยอดดูจากแอด
- ดึงข้อมูลแอดไม่ได้ → งานหลักไปต่อ ช่องแอดว่าง

ผลลัพธ์ (เขียนทับทุกรอบ)
- ชีต **Biopalm Content Insight — FB/IG/TikTok/YouTube 2026** แท็บ คำอธิบาย / FB โพสต์ / IG โพสต์ / TikTok โพสต์ / YouTube วิดีโอ / สรุปรายเดือน
- vault private `biopalm-insight`: `Content/<FB|IG|TikTok|YouTube>/<เดือน>/<วันที่> <ช่องทาง> <ประเภท> <ID>.md`, `Content/สรุปคอนเทนต์.md`, `.vault/content/posts.json`
- `.vault/content/monthly.json` สรุปรายเดือนแบบย่อ (จำนวนโพสต์ · ยอดดู · ทำแอด · 3 โพสต์ออร์แกนิกยอดดูสูงสุด) + ค่าแอด TikTok / Google Ads รายเดือนทั้งบัญชี → งาน `obsidian-vault` อ่านไปใส่โน้ต `Monthly/` ทุกเช้า
- โพสต์เดียวกันที่ลงหลายช่องทาง (แคปชัน/ชื่อคลิปขึ้นต้นเหมือนกัน วันที่ห่าง ≤ 60 วัน) ลิงก์หากันในโน้ต + ตารางเทียบในสรุป

รัน: GitHub Actions `obsidian-content` — ทุกวันจันทร์อัตโนมัติ หรือกด Run workflow (ใส่ `since` ได้ / ติ๊ก dry_run เพื่อลองดึงอย่างเดียว)

TikTok/YouTube พลาดได้โดยไม่ล้มงาน: ดึงไม่ได้ → ใช้ตัวเลขรอบก่อนจาก `.vault/content/posts.json` (อ่านผ่าน download_url เพราะไฟล์ใหญ่เกินคำตอบ Composio) ไม่เขียนแท็บ/โน้ตของช่องทางนั้นทับ และเตือนใน `สรุปคอนเทนต์` · โควตา YouTube ของ Composio ใช้ร่วมกับผู้ใช้อื่น บางรอบอาจเต็ม

ID บัญชีโฆษณา TikTok และช่อง YouTube อยู่ใน vault private `.vault/content/config.json` (`tiktok_advertiser_id`, `youtube_channel_id`) — repo นี้ public จึงไม่เขียน ID ไว้ในไฟล์ · ID เพจ FB / ชีต เทียบด้วย hash

ข้อจำกัด: FB วิดีโอยังไม่มีเวลาดู (Composio ไม่มีเครื่องมือ video_insights) · TikTok API ให้แค่ยอดดู/ไลก์/คอมเมนต์/แชร์ (ไม่มี reach/เวลาดู) และเฉพาะคลิปสาธารณะ · YouTube ช่องคอนเทนต์อยู่คนละอีเมล จึงไม่มีเวลาดู/ซับใหม่รายคลิป · Shorts ไม่มีช่องบอกใน API — ตรวจด้วยการเปิด `youtube.com/shorts/<ID>` (เปิดไม่ได้ → เดาจากความยาว) · Stories ย้อนหลังไม่ได้

หมายเหตุ FB: เครื่องมือรายการโพสต์ของ Composio ไม่รับ cursor `after` จึงไล่หน้าย้อนด้วย `until` (เวลาโพสต์เก่าสุดของหน้าก่อน) · ถ้าโพสต์เดียวแคปชันยาวจนคำตอบเกินขนาด จะเก็บโพสต์นั้นแบบไม่มีแคปชัน (ตัวเลขครบ)
