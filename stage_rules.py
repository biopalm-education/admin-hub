# -*- coding: utf-8 -*-
"""Shared chat rules for admin-hub (30 ก.ย. 2026) — one place for "แนบตัวอย่าง" and "สรุปจ่าย".

แนบตัวอย่าง (sample_type): a message from OUR side that carries
  - a link to a known sample (the 3 YouTube clips, the Drive folders ม.ปลาย / Module 1 / Module 2,
    the ม.ปลาย and ปรับพื้นฐาน short links)                                           -> 'clip'
  - or the words "ตัวอย่าง" / "ทดลองเรียน" together with any link:
        Google Form (ฟอร์มทดลองเรียนปรับพื้นฐาน, from 8 ก.ย.)                          -> 'trial'
        Drive / YouTube                                                                -> 'clip'
        anything else (review links, the YouTube channel)                              -> 'other'
  - the 3 known trial forms (TRIAL) count even as a bare link                          -> 'trial'
  - any link into the sample drive of 19 ส.ค. 2026 (sample_links.py: ปรับพื้นฐาน Module 1–4 videos -> 'clip',
    their PDFs -> 'doc', ข้อสอบประเมิน forms / exam PDFs -> 'trial'), even as a bare link
  - keyword now also "แบบทดสอบ" / "ข้อสอบประเมิน" (not in Giveaway messages)
  Only messages sent from 19 ส.ค. 2026 on count (sample_at) — the team's start date for the new samples.
  Not samples (checked ส.ค.–ก.ย.): the registration form after payment, Giveaway exam forms, shared FB posts of free
  content, FB comment-reply system links.
  Links are normalised to the file / clip id first, so a link copied from a phone and the same link copied
  from a computer (youtu.be vs youtube.com/watch, ?usp=sharing vs ?usp=drive_link, /mobile/) are one link.
  Checked against the real chats Mar–Sep 2026: the template "แอดมินขออนุญาตแนบคลิปทดลองเรียน…" started
  20–26 Mar 2026 on Facebook and LINE.

สรุปจ่าย (summary_marks): the payment summary card — within 30 minutes our side sent ALL of
  (1) "สรุปรายละเอียด" or "รหัสคอร์ส"   (2) an amount (5,500 บาท / 4500.- / ราคา 5500)
  (3) the BioPalm account 166-3-63464-6 or "โอนชำระค่าเรียนได้ที่"
  Usually one message; admins sometimes send the account in a second message, hence the window.
  "แอดมินสรุปยอดชำระให้ซักครู่นะคะ" (a promise) does not count. Slip-check replies are ignored.
  Replaces the old "any price mention" rule, which counted ~8x too many chats (FB ก.ย. 1,647 -> 215).
"""
import re, datetime
from urllib.parse import urlsplit
from sample_links import DRIVE, FORMS

URL = re.compile(r'https?://[^\s<>"\'`)\]]+', re.I)
SK = re.compile(r'ตัวอย่าง|ทดลองเรียน|แบบทดสอบ|ข้อสอบประเมิน')
GIVE = re.compile(r'giveaway', re.I)            # Giveaway exam forms are prizes, not samples
# 30 ก.ย. 2026 (ทีมแอดมิน): นับการส่งตัวอย่างตั้งแต่ 19 ส.ค. 2026 เป็นต้นไป — วันที่สร้าง drive ตัวอย่างชุดใหม่
SAMPLE_FROM = int((datetime.datetime(2026, 8, 19) - datetime.datetime(2026, 1, 1)).total_seconds() // 60)
CLIP = {'yt:1lcHo7k-R5g', 'yt:4h6Wn0z46cg', 'yt:iFWz23NK-fY',
        'drive:folder:1YXE_bX9Vm0vObqVhWP3323SOBpavsTiq',      # คลิปตัวอย่างการสอน ม.ปลาย
        'drive:folder:1eNJO12ynlxKNHFKJKcmIb1Vv60eR790E',      # ทดลองเรียน Module 2
        'drive:folder:15rJ0C9RntwQlHKUIoGbk4ceGy-4gPW0U',      # ทดลองเรียน Module 1
        'shorturl.at/295VE', 'shorturl.at/s0Q1Z'}
TRIAL = {'docs:forms:1FAIpQLSc-ivH8bnCFeiHHcyH3p9lHVvQ7CS4ch3PT-CkFayECuRr6Vw',   # ฟอร์มทดลองเรียน (seen with "ทดลองเรียน"
         'docs:forms:1FAIpQLScr4Y4nFtnxrGLAPUTbkIUYoVAQsLxgHkuyFInqw04aYFrZcw',   #  in ส.ค.–ก.ย.; also sent as a bare link)
         'docs:forms:1FAIpQLSdm6eUXVMbR1OUV_YYqcAlmAHTM35bAE48aIqACKuqYlKjMbw',
         'docs:forms:1FAIpQLSf3Fvmkdt1Xz8XYMQm6OL8zMMJL1wcs1gwHq2e_Zo1cWn6A6A'}   # "แบบทดสอบ Module 1-4" (sent bare, ก.ย.)
ACC = re.compile(r'166\s*-?\s*3\s*-?\s*63464\s*-?\s*6|โอนชำระ(?:ค่าเรียน)?\s*ได้ที่')
SUMS = re.compile(r'สรุปรายละเอียด|รหัสคอร์ส')
AMT = re.compile(r'(?:\d{1,3},\d{3}|\d{4,5})(?:\.\d+)?\s*(?:บาท|฿|\.-)|ราคา\s*[:：]?\s*\d')
SLIPTXT = re.compile(r'ตรวจสอบสลิปสำเร็จ|ชื่อผู้รับ')
WIN = 30                                     # minutes

_RX = [(re.compile(r'drive\.google\.com/drive/(?:u/\d+/)?(?:mobile/)?folders/([\w-]+)', re.I), 'drive:folder:'),
       (re.compile(r'drive\.google\.com/file/d/([\w-]+)', re.I), 'drive:file:'),
       (re.compile(r'drive\.google\.com/open\?id=([\w-]+)', re.I), 'drive:id:'),
       (re.compile(r'(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)([\w-]{6,})', re.I), 'yt:'),
       (re.compile(r'youtube\.com/playlist\?list=([\w-]+)', re.I), 'ytlist:')]
_DOCS = re.compile(r'docs\.google\.com/(document|presentation|spreadsheets|forms)/d/(?:e/)?([\w-]+)', re.I)


def norm(u):
    u = re.sub(r'[.,;!]+$', '', u)
    m = _DOCS.search(u)
    if m: return 'docs:%s:%s' % (m.group(1), m.group(2))
    for rx, p in _RX:
        m = rx.search(u)
        if m: return p + m.group(1)
    try:
        s = urlsplit(u)
        return re.sub(r'^(www|m)\.', '', s.netloc) + s.path.rstrip('/')
    except Exception:
        return u[:60]


def _drive(u):
    """type of a link into the sample drive (sample_links.py), else None"""
    if u.startswith('drive:'): return DRIVE.get(u.rsplit(':', 1)[1])
    if u.startswith('docs:forms:'): return FORMS.get(u.rsplit(':', 1)[1]) and 'trial'
    return None


def sample_type(text):
    t = str(text or '')
    urls = [norm(u) for u in URL.findall(t)]
    if not urls: return None
    tys = [x for x in (_drive(u) for u in urls) if x]
    if tys: return 'trial' if 'trial' in tys else ('clip' if 'clip' in tys else tys[0])
    if any(u in CLIP for u in urls): return 'clip'
    if any(u in TRIAL for u in urls): return 'trial'
    if not SK.search(t) or GIVE.search(t): return None
    if any(u.startswith('docs:forms') or u.startswith('forms.gle') for u in urls): return 'trial'
    if any(u.startswith('drive:') or u.startswith('yt:') for u in urls): return 'clip'
    return 'other'


def sample_at(minute, text):
    """sample_type() for a message sent at `minute` (minutes since 1 ม.ค. 2026) — only from SAMPLE_FROM (19 ส.ค. 2026) on"""
    return sample_type(text) if minute >= SAMPLE_FROM else None


def summary_marks(msgs):
    """msgs: [(minute, ours: bool, text)] in time order -> indices of the message that completes a summary card"""
    out = []; win = []
    for i, (t, ours, x) in enumerate(msgs):
        if not ours: continue
        x = str(x or '')
        if SLIPTXT.search(x): continue
        win = [w for w in win if t - w[0] <= WIN]
        win.append((t, bool(ACC.search(x)), bool(SUMS.search(x)), bool(AMT.search(x))))
        if any(w[1] for w in win) and any(w[2] for w in win) and any(w[3] for w in win):
            out.append(i); win = []
    return out
