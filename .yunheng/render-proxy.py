#!/usr/bin/env python3
# Cline Gateway -> OpenAI 兼容中继代理（云机部署版，公网可达）
# 部署：scp 到云机，nohup python3 proxy.py & （端口 int(os.environ.get("PORT", "8899"))，0.0.0.0）
import json, time, os, calendar, threading, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request, urllib.error

GW = "https://api.cline.bot/api/v1"
CACHE = "/tmp/cline-token-cache.json"
# refreshToken 从环境变量 CLINE_REFRESH_TOKEN 读（Render 不提供持久文件系统）
LOCK = threading.Lock()

def load_cache():
    try: return json.load(open(CACHE))
    except Exception: return {}

def save_cache(c):
    json.dump(c, open(CACHE, "w"))

def bootstrap():
    c = load_cache()
    env_rt = os.environ.get("CLINE_REFRESH_TOKEN", "").strip()
    if env_rt and not c.get("refresh"):
        c = {"token": "", "refresh": env_rt, "exp": 0}
        save_cache(c)
    # 有 refresh 就够（token 可以现刷新）；原来要求 token+refresh 同时存在导致首启必崩
    if c.get("refresh"): return c
    print("bootstrap fail: 无 refreshToken", flush=True)
    return {"token": "", "refresh": "", "exp": 0}

def parse_exp(v):
    if isinstance(v, (int, float)): return int(v if v < 1e12 else v)
    s = str(v)
    try: return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")) * 1000
    except Exception: return 0

def do_refresh(c):
    body = json.dumps({"refreshToken": c["refresh"], "granttype": "refresh_token"}).encode()
    req = urllib.request.Request(GW + "/auth/refresh", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read())
    data = d.get("data", d)
    c["token"] = data["accessToken"]
    c["exp"] = parse_exp(data.get("expiresAt", 0))
    if data.get("refreshToken"): c["refresh"] = data["refreshToken"]
    save_cache(c)
    print("token refreshed, exp:", c["exp"], flush=True)

def ensure_token():
    with LOCK:
        try:
            c = bootstrap()
            if not c["refresh"]: return c
            if time.time() * 1000 > c.get("exp", 0) - 120_000:
                try: do_refresh(c)
                except Exception as e: print("refresh fail, cached:", e, flush=True)
            return c
        except Exception as e:
            print("ensure_token crash:", e, flush=True)
            return {"token": "", "refresh": "", "exp": 0}

def upstream(path, body, tok):
    if not tok.startswith("workos:"): tok = "workos:" + tok
    req = urllib.request.Request(GW + path, data=body, method="POST",
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=600)

def call(path, body):
    c = ensure_token()
    for attempt in range(2):
        try:
            return upstream(path, body, c["token"])
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 0:
                print("401 → refresh & retry", flush=True)
                with LOCK:
                    try: do_refresh(c)
                    except Exception as ex: print("401 refresh fail:", ex, flush=True)
                continue
            return e
        except Exception as e:
            return e

def parse_sse_stream(resp):
    buf = b""
    for line in resp:
        buf += line
        if b"\n\n" in buf:
            chunk, buf = buf.split(b"\n\n", 1)
            for ev in chunk.split(b"\n"):
                if ev.startswith(b"data:"):
                    raw = ev[5:].strip()
                    if raw and raw != b"[DONE]":
                        try: yield json.loads(raw)
                        except Exception: pass

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *a): print(time.strftime("%H:%M:%S"), fmt % a, flush=True)

    def _relay(self, method):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        path = self.path[3:] if self.path.startswith("/v1/") else self.path
        client_stream = False
        model = "?"
        if body:
            try:
                j = json.loads(body); client_stream = bool(j.get("stream"))
                model = j.get("model", "?")
                if not client_stream:
                    j["stream"] = True
                    body = json.dumps(j).encode()
            except Exception: pass
        print(f"REQ {model} client_stream={client_stream}", flush=True)
        r = call(path, body)
        if isinstance(r, Exception):
            self._json(502, {"error": {"message": f"relay: {r}"}}); return
        if not isinstance(r, urllib.request.Request) and getattr(r, "status", 200) != 200:
            raw = r.read()
            self._json(r.status, {"error": {"message": raw.decode(errors="replace")[:500]}})
            return

        if client_stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                while True:
                    chunk = r.read(4096)
                    if not chunk: break
                    self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
            except Exception: pass
            return

        parts = []
        content = ""
        usage = None; mid = None; model_name = None
        for ev in parse_sse_stream(r):
            if mid is None:
                mid = ev.get("id"); model_name = ev.get("model")
            ch = ev.get("choices") or []
            if ch:
                d = ch[0].get("delta") or {}
                content += d.get("content") or ""
            if ev.get("usage"): usage = ev["usage"]
        out = {
            "id": mid or "gen-relay", "object": "chat.completion",
            "created": int(time.time()), "model": model_name or model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                         "finish_reason": "stop"}],
            "usage": usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        b = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(b); self.wfile.flush()
        except Exception as e:
            print("assemble fail:", e, flush=True)

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _safe_get(self):
        try: self.do_GET()
        except Exception as e:
            try: self._json(500, {"error": {"message": "handler crash: " + str(e)}})
            except Exception: pass
    def do_POST(self): self._relay("POST")
    def do_GET(self): self._safe_get()
    def do_GET(self):
        # /debug 端点：回报进程实际看到的环境与状态（不打 token 值）
        if self.path.startswith("/debug"):
            env_keys = sorted(k for k in os.environ if not k.lower().startswith("render_"))
            env_keys = [k for k in env_keys if "TOKEN" not in k.upper() and "KEY" not in k.upper() and "SECRET" not in k.upper()]
            c = load_cache()
            self._json(200, {
                "port_env": os.environ.get("PORT"),
                "listen_intent": "env PORT or 8899",
                "env_keys": env_keys,
                "has_refresh_in_env": bool(os.environ.get("CLINE_REFRESH_TOKEN", "").strip()),
                "cache": {"has_token": bool(c.get("token")), "has_refresh": bool(c.get("refresh")), "exp": c.get("exp")},
                "cwd": os.getcwd(),
                "script_exists": os.path.exists(os.path.abspath(__file__)),
            }); return
        path = self.path[3:] if self.path.startswith("/v1/") else self.path
        if "models" not in path:
            self._json(404, {"error": "not found"}); return
        c = ensure_token()
        if not c["refresh"]:
            self._json(503, {"error": {"message": "no refresh token configured"}}); return
        tok = c["token"]
        if not tok.startswith("workos:"): tok = "workos:" + tok
        req = urllib.request.Request(GW + path,
            headers={"Authorization": "Bearer " + tok})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                self._json(200, json.loads(r.read()))
        except urllib.error.HTTPError as e:
            self._json(e.code, {"error": {"message": "upstream " + str(e.code)}})
        except Exception as e:
            self._json(502, {"error": {"message": str(e)}})

if __name__ == "__main__":
    # Render 默认注入 PORT=10000；本地/云机默认 8899
    port = int(os.environ.get("PORT", "8899"))
    bootstrap()
    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    print("cline-relay cloud listening :" + str(port), flush=True)
    srv.serve_forever()
