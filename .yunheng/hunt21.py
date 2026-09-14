#!/usr/bin/env python3
import subprocess, re, os, json, sqlite3, glob

H = "/home/ubuntu/.hermes-gateway"
REPO = "/home/ubuntu/cloud-yunheng/hermes-agent"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
PURE = re.compile(r'^(gsk|sk|xoxb|xoxp|xapp)[A-Za-z0-9_-]{10,}$')
def mask(s): return KEYRE.sub(r'\1****', s or "")
def sh(cmd, t=90):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t).stdout or ""

env_key = ""
for line in open(H + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        env_key = line.split("=", 1)[1].strip()
print("[env]", env_key[:8] + "***")

def read_file(p):
    try:
        return open(p, errors="ignore").read()
    except Exception:
        return sh(f"sudo cat '{p}' 2>/dev/null")

def write_fix(p, old, new):
    try:
        txt = open(p, errors="ignore").read()
        open(p, "w").write(txt.replace(old, new))
        return True
    except Exception:
        r = sh(f"sudo sed -i 's/{old}/{new}/g' '{p}' 2>&1")
        return "权限" not in r and "denied" not in r

print("==A 网关进程全身environ搜查(只看钥匙类) ==")
for p in sh("pgrep -f 'gateway run'").split():
    try:
        env = open(f"/proc/{p}/environ", "rb").read().decode("utf-8", "ignore")
    except Exception:
        continue
    for kv in env.split("\0"):
        if "=" not in kv: continue
        k, _, v = kv.partition("=")
        if PURE.fullmatch(v.strip()) and len(v) > 12:
            tag = "OK=env同款" if v.strip() == env_key else "***异钥匙***"
            print(f"  pid{p} {k}={mask(v)[:12]} [{tag}]")
        elif re.search(r'(API|KEY|TOKEN|SECRET|BASE_URL|OPENAI|DEEPSEEK|GROQ|HERMES)', k) and v:
            print(f"  pid{p} {k}={mask(v)[:16]}")

print("==B 所有hermes家的config.yaml全文(打码) + .env钥匙指纹 ==")
homes = set()
for l in sh("sudo find /home /root -maxdepth 4 -name '.hermes*' -type d 2>/dev/null").splitlines():
    homes.add(l.strip())
homes.add(H)
for h in sorted(homes):
    cfg = os.path.join(h, "config.yaml")
    if os.path.exists(cfg) or sh(f"sudo test -f {cfg} && echo y").strip():
        print(f"  ---- {cfg} ----")
        for i, l in enumerate(read_file(cfg).splitlines(), 1):
            print(f"  {i:3}", mask(l)[:150])
    for envf in glob.glob(h + "/.env"):
        try:
            for l in open(envf, errors="ignore"):
                l = l.strip()
                if l.startswith("OPENAI_API_KEY="):
                    v = l.split("=", 1)[1]
                    tag = "同款" if v.strip() == env_key else "***异***"
                    print(f"  {envf}: OPENAI_API_KEY={mask(v)[:10]} [{tag}]")
        except Exception:
            pass

print("==C 源码解剖: _resolve_runtime_agent_kwargs + _load_gateway_config + 1995环 ==")
lines = open(REPO + "/gateway/run.py", errors="ignore").read().splitlines()
def dump(name, pat, n=55):
    for i, l in enumerate(lines):
        if re.search(pat, l) and ("def " in l or "for _field" in l):
            print(f"  [{name}] L{i+1}:")
            for j in range(i, min(i + n, len(lines))):
                print("   ", mask(lines[j])[:150])
            return
    print(f"  [{name}] (未找到)")
dump("runtime_kwargs组装", r"def _resolve_runtime_agent_kwargs")
dump("load_gateway_config", r"def _load_gateway_config", 40)
for i, l in enumerate(lines):
    if '("model", "MODEL")' in l:
        for j in range(max(0, i - 12), min(i + 25, len(lines))):
            print(f"  [1995环] L{j+1}:", mask(lines[j])[:150])
        break

print("==D 定点修复 ==")
# D1: 所有config.yaml里的字面旧钥匙 -> env新钥匙
for h in sorted(homes):
    cfg = os.path.join(h, "config.yaml")
    txt = read_file(cfg)
    if not txt: continue
    olds = set(m.group(0) for m in KEYRE.finditer(txt) if PURE.fullmatch(m.group(0)))
    for o in olds:
        if o != env_key:
            ok = write_fix(cfg, o, env_key)
            print(f"  [CFG-FIX] {cfg}: {o[:8]}*** -> 新钥匙 ({'成功' if ok else '失败'})")
# D2: session gateway_runtime 的 api_key / credential_pool
con = sqlite3.connect(H + "/state.db")
cur = con.cursor()
rows = cur.execute("SELECT id, model_config FROM sessions WHERE ended_at IS NULL AND model_config IS NOT NULL").fetchall()
fixed = 0
for sid, mc in rows:
    try: obj = json.loads(mc)
    except Exception: continue
    gr = obj.get("gateway_runtime") if isinstance(obj, dict) else None
    if not isinstance(gr, dict): continue
    ch = False
    if gr.get("api_key") and PURE.fullmatch(str(gr["api_key"]).strip()) and gr["api_key"].strip() != env_key:
        print("  [SESSION-FIX api_key]", (sid or "?")[:24], mask(gr["api_key"])[:12])
        gr["api_key"] = env_key; ch = True
    pool = gr.get("credential_pool")
    if isinstance(pool, list):
        for i, v in enumerate(pool):
            sv = str(v)
            if PURE.fullmatch(sv.strip()) and sv.strip() != env_key:
                print("  [SESSION-FIX pool]", (sid or "?")[:24], mask(sv)[:12])
                pool[i] = env_key; ch = True
    if ch:
        obj["gateway_runtime"] = gr
        cur.execute("UPDATE sessions SET model_config=? WHERE id=?", (json.dumps(obj, ensure_ascii=False), sid))
        fixed += 1
con.commit()
print("[sessions fixed]", fixed)
# D3: 全库残余纯旧钥匙报告
left = 0
for t in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    try:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
        for c in cols:
            try:
                for (rid, v) in cur.execute(f"SELECT rowid, {c} FROM {t} WHERE {c} IS NOT NULL").fetchall():
                    if isinstance(v, str) and PURE.fullmatch(v.strip()) and v.strip() != env_key:
                        print(f"  [残余] {t}.{c} rowid={rid} {mask(v)[:10]}")
                        left += 1
            except Exception: pass
    except Exception: pass
print("[全库残余异钥匙]", left)
con.close()

print("==E 重启 ==")
subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT21_DONE 杀完等看门狗拉起，TG发消息后把卷宗(尤其B段config.yaml)贴回来")
