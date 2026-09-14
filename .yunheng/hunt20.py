#!/usr/bin/env python3
import sqlite3, re, json, subprocess, os

H = "/home/ubuntu/.hermes-gateway"
REPO = "/home/ubuntu/cloud-yunheng/hermes-agent"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(r'\1****', s)
def sh(cmd, t=60):
    return (subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t).stdout or "")

env_key = ""
for line in open(H + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        env_key = line.split("=", 1)[1].strip()
print("[env]", env_key[:8] + "***")

print("==A run.py 源码裁决: runtime api_key 哪来的 ==")
src = open(REPO + "/gateway/run.py", errors="ignore").read().splitlines()
def show(a, b, tag):
    print(f"  [{tag}] L{a}:")
    for i in range(a - 1, min(b, len(src))):
        print("   ", mask(src[i])[:150])
show(2270, 2345, "api_key赋值现场")
show(2880, 2975, "_load_gateway_runtime_config函数体")

print("==B get_secret 定义 ==")
out = sh(f"grep -rn --exclude-dir=hermes-venv --include=*.py 'def get_secret' {REPO} | head -3")
print(out.strip() or "(无)")
m = re.search(r'([^:]+\.py):(\d+):', out)
if m:
    lines = open(m.group(1), errors="ignore").read().splitlines()
    st = int(m.group(2))
    for l in lines[st - 1:st + 22]:
        print("   ", mask(l)[:160])

print("==C 活跃会话 gateway_runtime 字段名全亮相(值打码) ==")
con = sqlite3.connect(H + "/state.db")
cur = con.cursor()
rows = cur.execute("SELECT id, model_config FROM sessions WHERE ended_at IS NULL AND model_config IS NOT NULL").fetchall()
for sid, mc in rows:
    try:
        obj = json.loads(mc)
    except Exception:
        print("  ", (sid or "?")[:24], "(json坏)"); continue
    gr = obj.get("gateway_runtime") if isinstance(obj, dict) else None
    if isinstance(gr, dict):
        g = {k: (mask(str(v))[:12] + "…" if isinstance(v, str) and len(str(v)) > 12 else v) for k, v in gr.items()}
        print("  ", (sid or "?")[:24], json.dumps(g, ensure_ascii=False)[:280])
    else:
        print("  ", (sid or "?")[:24], "(无gateway_runtime)")

print("==D 全库JSON内嵌api_key搜查(所有表) ==")
for t in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    try:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
        for c in cols:
            try:
                for (rid, v) in cur.execute(f"SELECT rowid, {c} FROM {t} WHERE {c} IS NOT NULL").fetchall():
                    if isinstance(v, str) and '"api_key"' in v and len(v) < 30000:
                        i = v.find('"api_key"')
                        print(f"  [EMBED] {t}.{c} rowid={rid}:", mask(v[max(0, i - 20):i + 80])[:150])
            except Exception:
                pass
    except Exception:
        pass

print("==E 修复: 活跃会话 gateway_runtime.api_key -> env新钥匙 ==")
fixed = 0
for sid, mc in rows:
    try:
        obj = json.loads(mc)
    except Exception:
        continue
    gr = obj.get("gateway_runtime") if isinstance(obj, dict) else None
    if isinstance(gr, dict) and "api_key" in gr and gr["api_key"] != env_key:
        old = str(gr["api_key"])
        gr["api_key"] = env_key
        obj["gateway_runtime"] = gr
        cur.execute("UPDATE sessions SET model_config=? WHERE id=?", (json.dumps(obj, ensure_ascii=False), sid))
        fixed += 1
        print("  [FIXED]", (sid or "?")[:24], "旧:", mask(old)[:14])
con.commit()
print("[fixed]", fixed)

print("==F 清理hunt19误伤 ==")
for f in [H + "/.skills_prompt_snapshot.json", H + "/models_dev_cache.json"]:
    if os.path.exists(f):
        os.remove(f)
        print("  已删(自动重建):", os.path.basename(f))
print("  .env 变量名盘点(值打码):")
for line in open(H + "/.env"):
    line = line.strip()
    if line and not line.startswith("#"):
        k, _, v = line.partition("=")
        print("   ", k, "=", (mask(v)[:14] if v else "(空)"))

print("==G messages 599/629 出处 ==")
try:
    for r in cur.execute("SELECT rowid, session_id, substr(content,1,60) FROM messages WHERE rowid IN (599,629)"):
        print("  ", r[0], (r[1] or "?")[:24], mask(r[2]))
except Exception as e:
    print("  ", e)
con.close()

subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT20_DONE 已杀网关等看门狗拉起，TG发消息；Slack token误伤等结案后重贴")
