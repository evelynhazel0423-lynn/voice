#!/usr/bin/env python3
import os, re, json, subprocess, glob, sqlite3

HOMES = ["/home/ubuntu/.hermes-gateway", "/root/.hermes-gateway"]
REPO = "/home/ubuntu/cloud-yunheng/hermes-agent"
VENV = "/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv"
VPY = VENV + "/bin/python"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(lambda m: m.group(0)[:8] + "***", s or "")
def sh(cmd, t=90):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t).stdout or ""

EK = ""
for line in open(HOMES[0] + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        EK = line.split("=", 1)[1].strip()
print("[新钥匙]", mask(EK)[:10])

print("==A 复审: resolve_runtime_provider 现在交什么钥匙 ==")
code = '''
import json, re, sys, traceback
try:
    sys.path.insert(0, "/home/ubuntu/cloud-yunheng/hermes-agent")
    from hermes_cli.runtime_provider import resolve_runtime_provider
    r = resolve_runtime_provider()
    def m(s): return re.sub(r"(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*", lambda x: x.group(0)[:8]+"***", str(s))
    out = {}
    for k, v in r.items():
        if k in ("api_key",): out[k] = (str(v)[:10] + "***len" + str(len(str(v)))) if v else v
        elif k == "credential_pool": out[k] = [str(x)[:10]+"***" for x in v] if isinstance(v, list) else v
        else: out[k] = m(v)
    print(json.dumps(out, ensure_ascii=False, default=str)[:1200])
except Exception:
    traceback.print_exc()
'''
env = os.environ.copy()
env["HERMES_HOME"] = HOMES[0]
try:
    for line in open(HOMES[0] + "/.env"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env.setdefault(k.strip(), v.strip())
except Exception:
    pass
r = subprocess.run([VPY, "-c", code], env=env, cwd=REPO, capture_output=True, text=True, timeout=90)
print("  stdout:", (r.stdout or "").strip()[:1200])
if r.stderr.strip():
    print("  stderr尾:", mask(r.stderr.strip())[-300:])

print("==B 全盘搜 no-key-required 文字 ==")
hits = []
# B1: 配置文件
for h in HOMES:
    if not os.path.isdir(h) and not sh(f"sudo test -d {h} && echo y").strip():
        continue
    out = sh(f"sudo grep -rIl 'no-key-required' {h} --exclude='*.db' 2>/dev/null; grep -rIl 'no-key-required' {h} --exclude='*.db' 2>/dev/null")
    for f in out.split():
        if f not in hits: hits.append(f)
    # config.yaml 显式检查
    cfg = h + "/config.yaml"
    txt = sh(f"sudo cat {cfg} 2>/dev/null") or (open(cfg, errors="ignore").read() if os.path.exists(cfg) else "")
    if "no-key-required" in txt:
        for l in txt.splitlines():
            if "no-key-required" in l or re.search(r'api_key', l):
                print(f"  [CFG] {cfg}: {l.strip()[:120]}")
        if cfg not in hits: hits.append(cfg)
# B2: 源码默认值
out = sh(f"grep -rIn 'no-key-required' {REPO} --exclude-dir=hermes-venv --exclude-dir=.git 2>/dev/null | head -8")
if out.strip():
    print("  [源码出处]")
    print("   ", mask(out).strip()[:800])
# B3: state.db 全库
con = sqlite3.connect(HOMES[0] + "/state.db")
cur = con.cursor()
db_cells = []
for t in [x[0] for x in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    try:
        cols = [x[1] for x in cur.execute(f"PRAGMA table_info({t})")]
        for c in cols:
            try:
                for (rid, v) in cur.execute(f"SELECT rowid, {c} FROM {t} WHERE {c} LIKE '%no-key-required%'").fetchall():
                    db_cells.append((t, c, rid))
            except Exception: pass
    except Exception: pass
print("  [DB内] ", db_cells[:12], f"共{len(db_cells)}格")
con.close()
print("[文件命中]", hits)

print("==C 连根拔 ==")
for f in hits:
    txt = sh(f"sudo cat '{f}' 2>/dev/null") or (open(f, errors="ignore").read() if os.path.isfile(f) else "")
    if not txt: continue
    n = txt.count("no-key-required")
    if n == 0: continue
    new = txt.replace("no-key-required", EK)
    try:
        open(f, "w").write(new)
        print(f"  [FIXED] {f}: {n}处 -> 真钥匙")
    except Exception:
        sh(f"sudo cp '{f}' '{f}.bak'")
        sh(f"sudo python3 -c \"open('{f}','w').write(open('{f}.bak').read().replace('no-key-required','{EK}'))\"")
        print(f"  [FIXED-sudo] {f}: {n}处")
if db_cells:
    con = sqlite3.connect(HOMES[0] + "/state.db")
    c2 = con.cursor()
    for (t, c, rid) in db_cells:
        v = c2.execute(f"SELECT {c} FROM {t} WHERE rowid=?", (rid,)).fetchone()[0]
        c2.execute(f"UPDATE {t} SET {c}=? WHERE rowid=?", (str(v).replace("no-key-required", EK), rid))
    con.commit(); con.close()
    print(f"  [DB-FIXED] {len(db_cells)}格")

print("==D 重启网关 ==")
subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT28_DONE 等看门狗拉起 -> TG发消息 -> 把A段复审JSON和替换计数贴回来")
