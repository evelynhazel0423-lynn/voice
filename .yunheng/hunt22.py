#!/usr/bin/env python3
import re, subprocess, os, json, sqlite3

H = "/home/ubuntu/.hermes-gateway"
REPO = "/home/ubuntu/cloud-yunheng/hermes-agent"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(r'\1****', s or "")
def sh(cmd, t=60):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t).stdout or ""

env_key = ""
for line in open(H + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        env_key = line.split("=", 1)[1].strip()
print("[env]", env_key[:8] + "*** len=" + str(len(env_key)))

def dump(path, pats, ctx):
    try:
        lines = open(path, errors="ignore").read().splitlines()
    except Exception as e:
        print("  (读不到)", path, e); return
    for pat in pats:
        for i, l in enumerate(lines):
            if re.search(pat, l):
                print(f"  ---- {os.path.basename(path)} :: {pat} @ L{i+1} ----")
                for j in range(i, min(i + ctx, len(lines))):
                    print("   ", mask(lines[j])[:160])
                break

print("==A runtime_provider.py: 发钥匙的人 ==")
dump(REPO + "/hermes_cli/runtime_provider.py",
     [r"def resolve_runtime_provider", r"def _get_model_config", r"def format_runtime_provider_error", r"fallback"], 90)

print("==B auth.py / env_loader.py: 秘密存储链 ==")
dump(REPO + "/hermes_cli/auth.py", [r"def get_secret", r"keychain|keyring|credential_store|\.json"], 45)
dump(REPO + "/hermes_cli/env_loader.py", [r"def get_secret"], 40)

print("==C config.py: 读哪个config+变量展开 ==")
dump(REPO + "/hermes_cli/config.py", [r"def get_config_path", r"def read_raw_config", r"def _expand_env_vars"], 40)

print("==D 两个hermes家全屋递归搜钥匙+config全文 ==")
for home in [H, "/root/.hermes-gateway"]:
    if not os.path.isdir(home) and not sh(f"sudo test -d {home} && echo y").strip():
        print(f"  ({home} 不存在)"); continue
    print(f"  ---- {home} 递归搜钥匙 ----")
    out = sh(f"sudo grep -rInE '(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{{20,}}' {home} --exclude-dir=logs --exclude='*.db' 2>/dev/null | head -30")
    print(mask(out).strip()[:2200] or "  (无)")
    cfgtxt = sh(f"sudo cat {home}/config.yaml 2>/dev/null")
    if cfgtxt.strip():
        print(f"  ---- {home}/config.yaml 全文(打码) ----")
        print("\n".join("   " + mask(l)[:150] for l in cfgtxt.splitlines())[:2600])

print("==E 钥匙活性复核(网关进程外直接打Groq) ==")
code = subprocess.run(["curl", "-s", "-m", "15", "https://api.groq.com/openai/v1/chat/completions",
                       "-H", f"Authorization: Bearer {env_key}", "-H", "Content-Type: application/json",
                       "-d", '{"model":"openai/gpt-oss-120b","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'],
                      capture_output=True, text=True, timeout=25).stdout
print("  HTTP body head:", code[:120].replace("\n", " "))

print("==F 布蜜罐: 活跃TG会话指到本机9999 ==")
HONEYPOT = r'''from http.server import BaseHTTPRequestHandler, HTTPServer
import json, datetime
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); body = self.rfile.read(n)
        with open("/tmp/honeypot.log", "a") as f:
            f.write(json.dumps({"t": datetime.datetime.now().isoformat(), "path": self.path,
                                "auth": self.headers.get("Authorization"),
                                "xapi": self.headers.get("x-api-key"),
                                "body_head": body[:160].decode("utf-8", "ignore")}) + "\n")
        self.send_response(401); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(b'{"error":{"message":"honeypot","type":"invalid_request_error","code":"invalid_api_key"}}')
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", 9999), H).serve_forever()'''
open("/tmp/honeypot.py", "w").write(HONEYPOT)
open("/tmp/honeypot.log", "w").close()
con = sqlite3.connect(H + "/state.db")
cur = con.cursor()
rows = cur.execute("SELECT id, billing_base_url, model_config FROM sessions WHERE ended_at IS NULL AND source='telegram'").fetchall()
backup = []
for sid, burl, mc in rows:
    backup.append({"id": sid, "billing": burl, "mc": mc})
    cur.execute("UPDATE sessions SET billing_base_url='http://127.0.0.1:9999/v1' WHERE id=?", (sid,))
    if mc:
        try:
            obj = json.loads(mc)
            gr = obj.get("gateway_runtime")
            if isinstance(gr, dict):
                gr["base_url"] = "http://127.0.0.1:9999/v1"
                obj["gateway_runtime"] = gr
                cur.execute("UPDATE sessions SET model_config=? WHERE id=?", (json.dumps(obj, ensure_ascii=False), sid))
        except Exception:
            pass
con.commit(); con.close()
json.dump(backup, open("/tmp/hp_state.json", "w"))
print("  [蜜罐已布]", len(backup), "个活跃TG会话 -> 127.0.0.1:9999")

subprocess.Popen(["python3", "/tmp/honeypot.py"], stdout=open("/tmp/honeypot_srv.log", "w"),
                 stderr=subprocess.STDOUT, start_new_session=True)
subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT22_DONE 蜜罐已就位+网关已重启中。现在去TG发一条(必失败,正常)，然后立刻跑 hunt23")
