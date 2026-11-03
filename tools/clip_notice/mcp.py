# -*- coding: utf-8 -*-
"""Composio MCP client สำหรับงาน clip-notice (สำเนาย่อจาก tools/meta_ads/composio_shim.py — แยกไฟล์เพื่อไม่กระทบงานเดิม)

ต่างจากตัวเดิมข้อเดียว: ส่ง account ที่ระบุมาทุกครั้ง (บัญชี Drive มี 2 บัญชี ต้องระบุเสมอ)
    run_composio_tool(slug, arguments, account=...) -> (res, err)   res['data'] = payload ของ tool, err = '' เมื่อสำเร็จ
log ไม่พิมพ์คำตอบของ tool (repo public)
"""
import os, json, time, threading
import requests

MCP_URL = os.environ.get('COMPOSIO_MCP_URL') or 'https://connect.composio.dev/mcp'
_KEY = (os.environ.get('COMPOSIO_API_KEY') or '').strip()
_sess = None
_lock = threading.Lock()


class _MCP(object):
    AUTH_MODES = ('both', 'consumer', 'bearer')

    def __init__(self, url, key):
        self.url, self.key, self.sid, self.rid, self.auth_mode = url, key, None, 0, 'both'

    def _headers(self):
        h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        if self.auth_mode in ('both', 'consumer'):
            h['x-consumer-api-key'] = self.key
        if self.auth_mode in ('both', 'bearer'):
            h['Authorization'] = 'Bearer ' + self.key
        if self.sid:
            h['Mcp-Session-Id'] = self.sid
        return h

    def _post(self, payload, timeout=180):
        r = requests.post(self.url, json=payload, headers=self._headers(), timeout=timeout)
        r.encoding = 'utf-8'
        for k in ('Mcp-Session-Id', 'mcp-session-id'):
            if r.headers.get(k):
                self.sid = r.headers[k]
                break
        if r.status_code >= 400:
            raise RuntimeError('HTTP %d' % r.status_code)
        body = r.text or ''
        if 'text/event-stream' not in (r.headers.get('content-type') or ''):
            return json.loads(body) if body.strip() else {}
        msgs, data = [], []

        def flush():
            if data:
                chunk = '\n'.join(data)
                del data[:]
                try:
                    msgs.append(json.loads(chunk))
                except Exception:
                    pass

        for line in body.split('\n'):
            line = line.rstrip('\r')
            if line == '':
                flush()
            elif line.startswith('data:'):
                v = line[5:]
                data.append(v[1:] if v.startswith(' ') else v)
        flush()
        for m in reversed(msgs):
            if isinstance(m, dict) and ('result' in m or 'error' in m):
                return m
        raise RuntimeError('SSE ไม่มีคำตอบ JSON-RPC (bytes=%d)' % len(body))

    def _rpc(self, method, params=None, timeout=180):
        self.rid += 1
        req = {'jsonrpc': '2.0', 'id': self.rid, 'method': method}
        if params is not None:
            req['params'] = params
        resp = self._post(req, timeout=timeout)
        if not isinstance(resp, dict):
            raise RuntimeError('คำตอบไม่ใช่ JSON-RPC')
        if resp.get('error'):
            raise RuntimeError('JSON-RPC error %s' % str((resp['error'] or {}).get('code')))
        return resp.get('result') or {}

    def connect(self):
        init = {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'clip-notice', 'version': '1.0'}}
        errs = []
        for mode in self.AUTH_MODES:
            self.auth_mode, self.sid = mode, None
            try:
                self._rpc('initialize', init, timeout=60)
                break
            except Exception as e:
                errs.append('%s: %s' % (mode, str(e)[:80]))
        else:
            raise RuntimeError('ล็อกอิน Composio MCP ไม่ผ่าน: ' + ' | '.join(errs))
        try:
            self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, timeout=60)
        except Exception:
            pass
        return self

    def call(self, name, arguments, timeout=170):
        res = self._rpc('tools/call', {'name': name, 'arguments': arguments}, timeout=timeout)
        if res.get('isError'):
            raise RuntimeError('tool error')
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
                raise RuntimeError('ไม่พบ COMPOSIO_API_KEY')
            _sess = _MCP(MCP_URL, _KEY).connect()
        return _sess


def _drop(c):
    global _sess
    with _lock:
        if _sess is c:
            _sess = None


def _dig(obj, slug):
    """ดึง payload ของ tool ออกจากคำตอบ COMPOSIO_MULTI_EXECUTE_TOOL (อาจห่อหลายชั้น)"""
    if not isinstance(obj, dict):
        return None, 'คำตอบไม่ใช่ dict'
    res = obj.get('results')
    if res is None and isinstance(obj.get('data'), dict):
        res = obj['data'].get('results')
    if isinstance(res, list) and res:
        item = next((x for x in res if isinstance(x, dict) and x.get('tool_slug') == slug), res[0])
        if isinstance(item, dict):
            if isinstance(item.get('response'), dict):
                item = item['response']
            if item.get('error'):
                return None, str(item['error'])[:200]
            if item.get('successful') is False:
                return None, 'tool reported failure'
            if 'data' not in item:
                return None, 'ไม่พบ data ในคำตอบ'
            return {'data': item['data']}, ''
    if obj.get('error'):
        return None, str(obj['error'])[:200]
    if isinstance(obj.get('data'), dict) and ('response' in obj['data'] or 'results' in obj['data']):
        return _dig(obj['data'], slug)
    if 'data' in obj:
        return {'data': obj['data']}, ''
    return {'data': obj}, ''


def run_composio_tool(tool_slug, arguments, *, account=None, tries=4):
    last, c = 'unknown error', None
    for i in range(tries):
        try:
            c = _client()
            item = {'tool_slug': tool_slug, 'arguments': dict(arguments or {})}
            if account:
                item['account'] = account
            raw = c.call('COMPOSIO_MULTI_EXECUTE_TOOL', {'tools': [item], 'sync_response_to_workbench': False})
            out, err = _dig(raw, tool_slug)
            if out is not None:
                return out, ''
            last = err or 'แกะคำตอบไม่ได้'
        except Exception as e:
            last = '%s: %s' % (type(e).__name__, str(e)[:200])
            if c is not None:
                _drop(c)
        if i + 1 < tries:
            time.sleep(3 * (2 ** i))
    return {}, last
