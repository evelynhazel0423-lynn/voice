#!/usr/bin/env python3
import re, subprocess, sqlite3, os

H = "/home/ubuntu/.hermes-gateway"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')

def mask(s): return KEYRE.sub(r'\1****', s)

def tail(path, pat=None, n=6):
    try:
        lines = open(path, errors='ignore').read().splitlines()
    except Exception:
        return []
    if pat:
        lines = [l for l in lines if re.search(pat, l)]
    return lines[-n:]

print("==1 最新401现场(errors.log)==")
for l in tail(H + "/logs/errors.log", r'API call failed|provider=|Non-retryable', 8):
    print(mask(l)[:240])

print("==2 gateway.log 尾巴==")
for l in tail(H + "/logs/gateway.log", None, 10):
    print(mask(l)[:240])

print("==3 重启史==")
for l in tail(H + "/gateway-starts.log", None, 6):
    print(l[:160])

print("==4 现役进程==")
out = subprocess.run(["pgrep", "-af", "gateway run"], capture_output=True, text=True).stdout
print(out.strip() or "(没有网关进程!)")

print("==5 活跃会话整行体检(打码截断)==")
try:
    con = sqlite3.connect(H + "/state.db")
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM sessions WHERE ended_at IS NULL").fetchall()
    print(f"(活跃会话数: {len(rows)})")
    for r in rows:
        for k in r.keys():
            v = r[k]
            if v is None:
                continue
            s = str(v)
            if k == "id":
                print(" id:", s[:34]); continue
            print(f"   {k}: {mask(s)[:200]}")
        print("   ---")
    con.close()
except Exception as e:
    print("db err:", e)

print("==6 hunt15复扫(全库指纹+换钥匙)==")
if os.path.exists("/tmp/hunt15.py"):
    out = subprocess.run(["python3", "/tmp/hunt15.py"], capture_output=True, text=True, timeout=180)
    print(mask(out.stdout)[-2600:])
    if out.stderr.strip():
        print("STDERR:", mask(out.stderr)[-400:])
else:
    print("(hunt15不在/tmp，跳过复扫)")

subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT16_DONE 网关已杀，等看门狗2分钟拉起，再去TG发消息")
