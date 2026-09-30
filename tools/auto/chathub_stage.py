# -*- coding: utf-8 -*-
"""ขั้น chat-hub: เอาข้อมูลดิบที่รอบนี้เพิ่งดึงจาก Meta มาคำนวณด้วยสูตรชุดของ chat-hub แล้ว deploy ขึ้น chat-hub

  ดึง FB + IG ครั้งเดียว (ในรอบ admin-hub) → admin-hub ใช้สูตรปัจจุบัน · chat-hub ใช้สูตรที่ค้างไว้ที่ PIN
  ไม่ดึง Meta ซ้ำ ไม่เขียน Google Sheets ซ้ำ ไม่ใช้เครื่องผู้ใช้

ข้อตกลง (แก้ admin-hub ได้ทุกอย่าง ยกเว้นสองข้อนี้):
  - fb_pull(mo, tok) และ ig_pull(mo) ใน tools/auto/refresh.py ต้องคืนข้อมูลดิบรูปแบบเดิม
    ถ้าจำเป็นต้องเปลี่ยน ให้ย้าย PIN ของ chat-hub ไปด้วย ไม่งั้นขั้นนี้พัง (admin-hub ไม่กระทบ)
  - step "รันรอบอัปเดต" ใน refresh.yml ต้องเรียก `python tools/auto/chathub_stage.py` (ไฟล์นี้ต่อขั้น chat-hub เข้ากับ ci_run.py เอง)
อยากให้ chat-hub ใช้สูตรใหม่เมื่อไร = เปลี่ยน PIN เป็น commit ของ admin-hub ที่ต้องการ

secrets: CHATHUB_GH_TOKEN (ไม่มี = ใช้ ADMIN_GH_TOKEN) ต้องมีสิทธิ์เขียน repo chat-hub
         CHATHUB_SECRET   (ไม่มี = ใช้ ADMIN_SECRET)   ชื่อผู้ใช้:รหัสผ่านของหน้า chat-hub
ปิดขั้นนี้ชั่วคราวได้ด้วย repository variable CHATHUB=0
"""
import os, subprocess

PIN = '60fa224e95d31c7e3b96b4e1b9ca72afabe7f5eb'    # admin-hub 30 ก.ย. 2026 — สูตร metric ของ chat-hub
SRC = 'https://github.com/biopalm-education/admin-hub.git'
PIN_DIR = '/tmp/chpin'      # clone ของ admin-hub ที่ PIN
P = '/tmp/chp'              # สคริปต์ชุดของ chat-hub (สำเนาจาก PIN)
REPO = '/tmp/chb'           # clone ของ chat-hub ระหว่าง build


def _sh(cmd):
    subprocess.run(['bash', '-lc', cmd], check=True)


def _patch(path, reps):
    with open(path, encoding='utf-8') as f:
        s = f.read()
    for a, b in reps:
        if s.count(a) != 1:
            raise RuntimeError('แพตช์ %s ไม่ตรง (%s)' % (os.path.basename(path), a[:50]))
        s = s.replace(a, b)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)


def prepare():
    tok = (os.environ.get('CHATHUB_GH_TOKEN') or '').strip()
    sec = (os.environ.get('CHATHUB_SECRET') or os.environ.get('ADMIN_SECRET') or '').strip()
    if not tok:
        raise RuntimeError('ไม่พบ token ที่เขียน chat-hub ได้ — ตั้ง secret CHATHUB_GH_TOKEN หรือ ADMIN_GH_TOKEN')
    if ':' not in sec:
        raise RuntimeError('ไม่พบรหัสผ่านของ chat-hub — ตั้ง secret CHATHUB_SECRET (หรือ ADMIN_SECRET)')
    for name, val in (('/tmp/chathub_token.txt', tok), ('/tmp/chathub_secret.txt', sec)):
        with open(name, 'w', encoding='utf-8') as f:
            f.write(val)
        os.chmod(name, 0o600)

    _sh('rm -rf %s %s && git clone -q --filter=blob:none %s %s && git -C %s checkout -q %s'
        % (PIN_DIR, P, SRC, PIN_DIR, PIN_DIR, PIN))
    _sh('mkdir -p %s && cp -a %s/. %s/ && cd %s && rm -rf .git data preview app.html index.html manifest.json'
        % (P, PIN_DIR, P, P))

    clone = ("subprocess.run(['bash','-lc',f'rm -rf {REPO} && git clone -q --depth 1 "
             "https://github.com/{SLUG}.git {REPO}'],check=True)")
    _patch(P + '/tools/auto/refresh.py', [
        ("REPO='/tmp/ahb'; WORK='/tmp/bp'; SLUG='biopalm-education/admin-hub'",
         "REPO='%s'; WORK='/tmp/chbwork'; SLUG='biopalm-education/chat-hub'" % REPO),
        ("tok=open('/tmp/gh_token.txt').read().strip(); sec=open('/tmp/admin_secret.txt').read().strip()",
         "tok=open('/tmp/chathub_token.txt').read().strip(); sec=open('/tmp/chathub_secret.txt').read().strip()"),
        # หลัง clone chat-hub วางสคริปต์ชุดของ chat-hub ทับ ก่อน unpack / build / deploy (หน้าเว็บ app.html ของ chat-hub ไม่ถูกแตะ)
        (clone, clone + "\n    subprocess.run(['bash','-lc',f'cd %s && cp -r tools *.py deploy.sh {REPO}/'],check=True)" % P),
    ])
    _patch(P + '/deploy.sh', [
        ('REPO=$HOME/.admin-hub-deploy', 'REPO=$HOME/.chat-hub-deploy'),
        ('SLUG=biopalm-education/admin-hub', 'SLUG=biopalm-education/chat-hub'),
        ('echo "pushed · https://biopalm-education.github.io/admin-hub/"',
         'echo "pushed · https://biopalm-education.github.io/chat-hub/"'),
    ])


def _no_network(*a, **k):
    return {}, 'ขั้น chat-hub ใช้ข้อมูลดิบที่ดึงแล้วเท่านั้น'


def run(months, RAW):
    """RAW = {'fb': {mo: ผลของ fb_pull}, 'ig': {mo: ผลของ ig_pull}} ที่รอบ admin-hub เก็บไว้ (สำเนา ไม่ถูกแก้)"""
    miss = [m for m in months if m not in RAW['fb'] or m not in RAW['ig']]
    if miss:
        raise RuntimeError('ไม่มีข้อมูลดิบของเดือน %s' % ', '.join(miss))
    prepare()
    g = {'__name__': 'chb_refresh', 'run_composio_tool': _no_network}
    path = P + '/tools/auto/refresh.py'
    with open(path, encoding='utf-8') as f:
        exec(compile(f.read(), path, 'exec'), g)
    g['fb_token'] = lambda: ''
    g['fb_pull'] = lambda mo, tok: RAW['fb'][mo]
    g['ig_pull'] = lambda mo: RAW['ig'][mo]
    print('chat-hub: สูตรนับ admin-hub@%s · เดือน %s' % (PIN[:7], ', '.join(months)), flush=True)
    return g['run_refresh'](months)


# ---------------------------------------------------------------- ต่อเข้ากับรอบอัปเดตของ admin-hub
# refresh.yml เรียก `python tools/auto/chathub_stage.py` แทน `python tools/auto/ci_run.py`
# ไฟล์นี้อ่าน ci_run.py ที่ step "เขียนสคริปต์ช่วย" สร้างไว้ เติมจุดเก็บข้อมูลดิบ + เรียกขั้น chat-hub แล้วรันต่อ
# ถ้า ci_run.py ถูกแก้จนหาจุดต่อไม่เจอ: admin-hub ยังรันตามปกติทุกอย่าง แต่รอบนี้ขึ้น failed บอกให้ปรับไฟล์นี้

_HOOKS = [
    ("    g['ig_pull'] = ig_pull_checked\n",
     "    g['ig_pull'] = ig_pull_checked\n"
     "    import copy as _copy\n"
     "    RAW = {'fb': {}, 'ig': {}}          # สำเนาข้อมูลดิบให้ขั้น chat-hub (ไม่ดึงซ้ำ)\n"
     "    _fb_pull0 = g['fb_pull']\n"
     "\n"
     "    def _fb_pull_raw(mo, tok):\n"
     "        out = _fb_pull0(mo, tok)\n"
     "        RAW['fb'][mo] = _copy.deepcopy(out)\n"
     "        return out\n"
     "\n"
     "    g['fb_pull'] = _fb_pull_raw\n"),
    ("        CAP['ig'][mo] = out\n",
     "        CAP['ig'][mo] = out\n"
     "        RAW['ig'][mo] = _copy.deepcopy(out)\n"),
    ("    g['run_refresh'](months)\n    print('เสร็จ — หน้าเว็บอัปเดตแล้ว', flush=True)\n",
     "    if mode == 'chathub':               # ดึงดิบ → chat-hub อย่างเดียว (admin-hub และชีตไม่แตะ)\n"
     "        _tok = g['fb_token']()\n"
     "        for mo in months:\n"
     "            g['fb_pull'](mo, _tok)\n"
     "            g['ig_pull'](mo)\n"
     "        _CHATHUB_OK[0] = _chathub(months, RAW)\n"
     "        return\n"
     "    g['run_refresh'](months)\n    print('เสร็จ — หน้าเว็บอัปเดตแล้ว', flush=True)\n"
     "    _CHATHUB_OK[0] = _chathub(months, RAW)\n"),
]


def _chathub(months, RAW):
    """ขั้น chat-hub — พลาดแล้ว admin-hub ไม่กระทบ (คืน False ให้รอบนี้ขึ้น failed ตอนท้าย)"""
    if (os.environ.get('CHATHUB') or '1').strip().lower() in ('0', 'false', 'no', 'off'):
        print('ข้ามขั้น chat-hub (CHATHUB=0)', flush=True)
        return True
    try:
        done = run(months, RAW)
        print('chat-hub อัปเดตแล้ว:', ', '.join(done or months), flush=True)
        return True
    except Exception as e:
        print('::error title=chat-hub ไม่อัปเดต::%s: %s' % (type(e).__name__, str(e)[:400]), flush=True)
        return False


def main():
    import sys
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ci_run.py')
    with open(path, encoding='utf-8') as f:
        src = f.read()
    hook_err = ''
    for a, b in _HOOKS:
        if src.count(a) != 1:
            hook_err = 'ci_run.py เปลี่ยนไป หาจุดต่อขั้น chat-hub ไม่เจอ (%s) — ต้องปรับ tools/auto/chathub_stage.py' % a.strip()[:40]
            break
    if not hook_err:
        for a, b in _HOOKS:
            src = src.replace(a, b)
    ok = [None]                      # None = ขั้น chat-hub ไม่ได้รัน (selftest / ข้ามเพราะ ci_run หยุดก่อน)
    g = {'__name__': '__main__', '__file__': path, '_chathub': _chathub, '_CHATHUB_OK': ok}
    code, msgs = 0, []
    try:
        exec(compile(src, path, 'exec'), g)
    except SystemExit as e:
        if e.code not in (None, 0):
            code = 1
            if not isinstance(e.code, int):
                msgs.append(str(e.code))
    if hook_err:
        print('::error title=chat-hub ไม่อัปเดต::' + hook_err, flush=True)
        code, msgs = 1, msgs + ['admin-hub รันตามปกติ แต่ chat-hub ไม่อัปเดต: ' + hook_err]
    elif ok[0] is False:
        code, msgs = 1, msgs + ['chat-hub ไม่อัปเดต — ดูบรรทัด chat-hub ด้านบน']
    if code:
        sys.exit(' · '.join(msgs) or 1)


if __name__ == '__main__':
    main()
