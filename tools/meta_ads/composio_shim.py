# -*- coding: utf-8 -*-
"""run_composio_tool ที่คุยกับ Composio MCP server ตรง ๆ (ใช้ใน GitHub Actions) — สำเนาจาก refresh.yml ใช้กับงาน meta-ads-export

ไม่ใช้ composio SDK เพราะ key ของบัญชีนี้เป็น MCP consumer key (ck_...)
ซึ่งส่งใน header x-consumer-api-key ไม่ใช่ x-api-key ของ platform API

สัญญาเหมือน helper ของ workbench ทุกประการ:
    run_composio_tool(slug, arguments) -> (res, err)
    res['data'] คือ payload ของ tool, err เป็น '' เมื่อสำเร็จ
refresh.py จึงเรียกใช้ได้โดยไม่ต้องแก้อะไรเลย
"""
import os, re, json, time, threading
import requests

MCP_URL = os.environ.get('COMPOSIO_MCP_URL') or 'https://connect.composio.dev/mcp'
_KEY = (os.environ.get('COMPOSIO_API_KEY') or '').strip()
DEBUG = bool(os.environ.get('MCP_DEBUG'))
DRIVE_ACCOUNT = (os.environ.get('COMPOSIO_DRIVE_ACCOUNT') or 'googledrive_strown-skyre').strip()

_sess = None
_lock = threading.Lock()
# refresh.py ยิง IG พร้อมกัน 6 thread — Composio ตอบพลาดราว 20% (29 ก.ย.)
# จำกัดให้ยิงพร้อมกันไม่เกิน 3 และจดสาเหตุที่พลาดไว้รายงานท้ายรอบ
_gate = threading.BoundedSemaphore(int(os.environ.get('MCP_PARALLEL') or 3))
FAILS = {}


class _MCP(object):
    # เซิร์ฟเวอร์รับ key ได้หลายทาง ลองไล่จนกว่าจะผ่าน แล้วจำไว้ใช้ต่อ
    AUTH_MODES = ('both', 'consumer', 'bearer')

    def __init__(self, url, key):
        self.url = url
        self.key = key
        self.sid = None
        self.rid = 0
        self.tools = set()
        self.last_raw = ''
        self.last_reason = ''
        self.auth_ok = ''
        self.auth_mode = 'both'

    def _headers(self):
        h = {'Content-Type': 'application/json',
             'Accept': 'application/json, text/event-stream'}
        if self.auth_mode in ('both', 'consumer'):
            h['x-consumer-api-key'] = self.key
        if self.auth_mode in ('both', 'bearer'):
            h['Authorization'] = 'Bearer ' + self.key
        if self.sid:
            h['Mcp-Session-Id'] = self.sid
        return h

    def _post(self, payload, timeout=180):
        r = requests.post(self.url, json=payload, headers=self._headers(), timeout=timeout)
        # MCP ตอบเป็น UTF-8 เสมอ แต่ SSE ไม่ระบุ charset → requests เดาเป็น ISO-8859-1 ภาษาไทยจึงเพี้ยน (30 ก.ย.)
        r.encoding = 'utf-8'
        for k in ('Mcp-Session-Id', 'mcp-session-id'):
            if r.headers.get(k):
                self.sid = r.headers[k]
                break
        self.last_raw = (r.text or '')[:4000]
        self.last_reason = r.headers.get('x-mcp-auth-failure-reason') or ''
        if r.status_code >= 400:
            raise RuntimeError('HTTP %d%s: %s' % (
                r.status_code,
                (' [' + self.last_reason + ']') if self.last_reason else '',
                (r.text or '')[:300]))
        return self._decode(r)

    @staticmethod
    def _decode(r):
        # อ่าน SSE ตามสเปก: บรรทัด data: ที่ติดกันในเหตุการณ์เดียวต้องต่อกันด้วย \n
        # (ตัวอ่านเดิมอ่านทีละบรรทัด คำตอบก้อนใหญ่ที่ถูกแบ่งหลายบรรทัดจึงหายเป็น None)
        # และเลือกข้อความที่มี result/error ไม่ใช่ notification ที่มาทีหลัง
        body = r.text or ''
        ctype = r.headers.get('content-type') or ''
        if 'text/event-stream' not in ctype:
            if not body.strip():
                raise RuntimeError('คำตอบว่าง (content-type=%s)' % ctype[:40])
            return json.loads(body)
        msgs, data, stat = [], [], {'events': 0, 'data_lines': 0, 'bad': 0, 'names': []}

        def flush():
            if not data:
                return
            stat['events'] += 1
            chunk = '\n'.join(data)
            del data[:]
            if not chunk.strip() or chunk.strip() == '[DONE]':
                return
            try:
                msgs.append(json.loads(chunk))
            except Exception:
                stat['bad'] += 1

        for line in body.split('\n'):
            line = line.rstrip('\r')
            if line == '':
                flush()
            elif line.startswith('data:'):
                v = line[5:]
                data.append(v[1:] if v.startswith(' ') else v)
                stat['data_lines'] += 1
            elif line.startswith('event:') and len(stat['names']) < 5:
                stat['names'].append(line[6:].strip()[:20])
        flush()
        for m in reversed(msgs):
            if isinstance(m, dict) and ('result' in m or 'error' in m):
                return m
        # ไม่พบคำตอบ: บอกแค่โครง (ไม่มีเนื้อหาแชท) เพื่อหาสาเหตุต่อ
        raise RuntimeError('SSE ไม่มีคำตอบ JSON-RPC: bytes=%d events=%d data_lines=%d parse_fail=%d msgs=%d event_names=%s' % (
            len(body), stat['events'], stat['data_lines'], stat['bad'], len(msgs), stat['names']))

    def _rpc(self, method, params=None, timeout=180):
        self.rid += 1
        req = {'jsonrpc': '2.0', 'id': self.rid, 'method': method}
        if params is not None:
            req['params'] = params
        resp = self._post(req, timeout=timeout)
        if not isinstance(resp, dict):
            raise RuntimeError('คำตอบไม่ใช่ JSON-RPC: %s' % str(resp)[:200])
        if resp.get('error'):
            raise RuntimeError('JSON-RPC error: %s' % json.dumps(resp['error'])[:300])
        return resp.get('result') or {}

    def connect(self):
        init = {
            'protocolVersion': '2025-06-18',
            'capabilities': {},
            'clientInfo': {'name': 'meta-ads-export', 'version': '1.0'},
        }
        errs = []
        for mode in self.AUTH_MODES:
            self.auth_mode = mode
            self.sid = None
            try:
                self._rpc('initialize', init, timeout=60)
                self.auth_ok = mode
                break
            except Exception as e:
                errs.append('%s -> %s' % (mode, str(e)[:200]))
        else:
            raise RuntimeError('ล็อกอิน MCP ไม่ผ่านทุกวิธี:\n  ' + '\n  '.join(errs))
        try:
            self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, timeout=60)
        except Exception:
            pass
        try:
            cur = None
            for _ in range(10):
                p = {'cursor': cur} if cur else {}
                res = self._rpc('tools/list', p, timeout=60)
                for t in (res.get('tools') or []):
                    if t.get('name'):
                        self.tools.add(t['name'])
                cur = res.get('nextCursor')
                if not cur:
                    break
        except Exception as e:
            if DEBUG:
                print('tools/list ไม่สำเร็จ:', e)
        return self

    def call(self, name, arguments, timeout=170):
        res = self._rpc('tools/call', {'name': name, 'arguments': arguments}, timeout=timeout)
        if res.get('isError'):
            raise RuntimeError('tool error: %s' % json.dumps(res)[:300])
        sc = res.get('structuredContent')
        if isinstance(sc, dict) and sc:
            return sc
        for part in (res.get('content') or []):
            if part.get('type') == 'text' and part.get('text'):
                try:
                    return json.loads(part['text'])
                except Exception:
                    return {'_text': part['text']}
        return res


def _client():
    global _sess
    with _lock:
        if _sess is None:
            if not _KEY:
                raise RuntimeError('ไม่พบ COMPOSIO_API_KEY — ตั้งเป็น repo secret ก่อน')
            _sess = _MCP(MCP_URL, _KEY).connect()
        return _sess


def _drop(c):
    # รีเซ็ต session เฉพาะตัวที่พัง — refresh.py ยิง IG พร้อมกัน 6 thread
    global _sess
    with _lock:
        if _sess is c:
            _sess = None


_TOK = re.compile(r'(access_token=)[^&\s"\']+|\b(?:EAA|IGAA|IGQ)[A-Za-z0-9_\-]{20,}')


def redact(obj):
    # ห้าม token หลุดลง log — repo นี้เป็น public (รวม token ที่ฝังอยู่ในลิงก์ paging.next ของ IG)
    if isinstance(obj, dict):
        return {k: ('***' if 'token' in str(k).lower() else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        return _TOK.sub(lambda m: (m.group(1) or '') + '***', obj)
    return obj


def _dig(obj, slug):
    """ดึง payload ของ tool ออกมาจากคำตอบที่อาจถูกห่อหลายชั้น"""
    if not isinstance(obj, dict):
        return None, 'คำตอบไม่ใช่ dict'
    res = obj.get('results')
    if res is None and isinstance(obj.get('data'), dict):
        res = obj['data'].get('results')
    if isinstance(res, list) and res:
        item = None
        for x in res:
            if isinstance(x, dict) and x.get('tool_slug') == slug:
                item = x
                break
        item = item or res[0]
        if isinstance(item, dict):
            if isinstance(item.get('response'), dict):
                item = item['response']
            if item.get('error'):
                return None, str(item['error'])[:300]
            if item.get('successful') is False:
                return None, 'tool reported failure'
            if 'data' not in item:
                return None, 'ไม่พบ data ในคำตอบ (keys=%s)' % ','.join(sorted(map(str, item.keys()))[:8])
            return {'data': item['data']}, ''
    if obj.get('error'):
        return None, str(obj['error'])[:300]
    if isinstance(obj.get('data'), dict) and ('response' in obj['data'] or 'results' in obj['data']):
        return _dig(obj['data'], slug)
    if isinstance(obj.get('response'), dict):
        r = obj['response']
        if r.get('error') or r.get('successful') is False:
            return None, str(r.get('error') or 'tool reported failure')[:300]
        if 'data' in r:
            return {'data': r['data']}, ''
    if 'data' in obj:
        return {'data': obj['data']}, ''
    return {'data': obj}, ''


def run_composio_tool(tool_slug, arguments, retry_params=None, print_schema_for_tool=False, *, account=None):
    with _gate:
        out, err = _run(tool_slug, arguments, retry_params)
    if err:
        with _lock:
            n, _ = FAILS.get(tool_slug, (0, ''))
            FAILS[tool_slug] = (n + 1, redact(err)[:200])
    return out, err


def _run(tool_slug, arguments, retry_params=None):
    tries = int((retry_params or {}).get('max_retries', 4)) or 1
    delay = float((retry_params or {}).get('delay_ms', 3000)) / 1000.0
    last = 'unknown error'
    args = dict(arguments or {})
    # หน้าละ 25 ข้อความแทน 100 — คำตอบก้อนเล็กลงเมื่อผ่าน MCP · refresh.py ไล่ cursor ต่อเองจนครบเหมือนเดิม
    if tool_slug == 'INSTAGRAM_LIST_ALL_MESSAGES' and int(args.get('limit') or 0) > 25:
        args['limit'] = 25
    t0 = time.time()
    for i in range(tries):
        try:
            c = None
            c = _client()
            if tool_slug in c.tools:
                raw = c.call(tool_slug, args)
            else:
                item = {'tool_slug': tool_slug, 'arguments': args}
                if tool_slug.startswith('GOOGLEDRIVE_'):
                    item['account'] = DRIVE_ACCOUNT
                raw = c.call('COMPOSIO_MULTI_EXECUTE_TOOL', {
                    'tools': [item],
                    'sync_response_to_workbench': False,
                })
            if DEBUG:
                print('RAW[%s]: %s' % (tool_slug, json.dumps(redact(raw), ensure_ascii=False)[:1500]))
            out, err = _dig(raw, tool_slug)
            if out is not None:
                return out, ''
            last = err or 'แกะคำตอบไม่ได้'
            if 'data_preview' in last:
                # คำตอบใหญ่เกิน Composio ไม่ส่ง data กลับ — ลองซ้ำขนาดเดิมไม่ช่วย ให้ผู้เรียกลดขนาดหน้าเอง
                return {}, 'TOO_LARGE ' + last
        except Exception as e:
            last = '%s หลัง %.0f วินาที: %s' % (type(e).__name__, time.time() - t0, str(e)[:300])
            if c is not None:
                _drop(c)
        if i + 1 < tries:
            time.sleep(delay * (2 ** i))          # 3, 6, 12, 24 วินาที
    return {}, last
