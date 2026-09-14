#!/usr/bin/env python3
import os, re, json, subprocess, sqlite3

HOMES = ["/home/ubuntu/.hermes-gateway", "/root/.hermes-gateway"]
REPO = "/home/ubuntu/cloud-yunheng/hermes-agent"
VPY = "/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv/bin/python"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(lambda m: m.group(0)[:8] + "***", s or "")
def sh(cmd, t=120):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t).stdout or ""

EK = ""
for line in open(HOMES[0] + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        EK = line.split("=", 1)[1].strip()
print("[新钥匙]", mask(EK)[:10])

print("==A 两个家全部文件清单(无排除) ==")
allfiles = []
for h in HOMES:
    out = sh(f"sudo find {h} -maxdepth 2 -type f 2>/dev/null | head -60")
    for f in out.split():
        if f not in allfiles: allfiles.append(f)
    print(f"  {h}:")
    print("   " + "\n   ".join(os.path.basename(x) for x in out.split()[:40]))

print("==B 每个数据库全表搜no-key(这次一个不漏) ==")
dbs = [f for f in allfiles if f.endswith(".db")]
print("  [找到的db]", dbs)
dbfix = []
for db in dbs:
    try:
        con = sqlite3.connect(db)
        cur = con.cursor()
        for t in [x[0] for x in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
            cols = [x[1] for x in cur.execute(f"PRAGMA table_info({t})")]
            for c in cols:
                try:
                    rows = cur.execute(f"SELECT rowid, {c} FROM {t} WHERE CAST({c} AS TEXT) LIKE '%no-key%'").fetchall()
                    for (rid, v) in rows:
                        s = str(v)
                        i = s.lower().find("no-key")
                        print(f"  [HIT] {os.path.basename(db)}.{t}.{c} rowid={rid}: ...{mask(s[max(0,i-30):i+50])}...")
                        dbfix.append((db, t, c, rid))
                except Exception: pass
        con.close()
    except Exception as e:
        print("  (打不开)", db, e)

print("==C 活跃会话model_config内嵌api_key(打码亮值) ==")
con = sqlite3.connect(HOMES[0] + "/state.db")
cur = con.cursor()
mcfix = 0
for sid, mc in cur.execute("SELECT id, model_config FROM sessions WHERE ended_at IS NULL AND model_config IS NOT NULL").fetchall():
    if "no-key" in (mc or "").lower():
        i = mc.lower().find("no-key")
        print(f"  [MC-HIT] {sid[:24]}: ...{mask(mc[max(0,i-40):i+60])}...")
        cur.execute("UPDATE sessions SET model_config=? WHERE id=?", (mc.replace("no-key-required", EK), sid))
        mcfix += 1
con.commit(); con.close()
print("  [MC修复]", mcfix)

print("==D 全文件无死角grep(不排除任何扩展名) ==")
out = sh("sudo grep -rIl 'no-key-required' /home/ubuntu/.hermes-gateway /root/.hermes-gateway /etc/environment /home/ubuntu/.bashrc /home/ubuntu/.profile 2>/dev/null | head -20")
print(mask(out).strip()[:1000] or "  (无)")
for f in out.split():
    txt = sh(f"sudo cat '{f}'") or open(f, errors="ignore").read()
    n = txt.count("no-key-required")
    try:
        open(f, "w").write(txt.replace("no-key-required", EK))
        print(f"  [FIXED] {f}: {n}处")
    except Exception:
        sh(f"sudo sed -i 's/no-key-required/{EK}/g' '{f}'")
        print(f"  [FIXED-sudo] {f}: {n}处")

print("==E DB处决 ==")
if dbfix:
    for (db, t, c, rid) in dbfix:
        con = sqlite3.connect(db)
        v = con.execute(f"SELECT {c} FROM {t} WHERE rowid=?", (rid,)).fetchone()[0]
        con.execute(f"UPDATE {t} SET {c}=? WHERE rowid=?", (str(v).replace("no-key-required", EK), rid))
        con.commit(); con.close()
    print(f"  [DB-FIXED] {len(dbfix)}格")
else:
    print("  (DB无)")

print("==F hermes凭据存储源码定位 ==")
out = sh(f"grep -n -E 'auth\\.json|auth_store|credentials.*json|keyring|secrets' {REPO}/hermes_cli/auth.py 2>/dev/null | head -8")
print("  auth.py存储点:", mask(out).strip()[:600] or "(无)")

print("==G 复审(干净env硬覆盖) ==")
code = (
    "import json, sys\n"
    "sys.path.insert(0, \"/home/ubuntu/cloud-yunheng/hermes-agent\")\n"
    "from hermes_cli.runtime_provider import resolve_runtime_provider\n"
    "r = resolve_runtime_provider()\n"
    "k = str(r.get(\"api_key\", \"\"))\n"
    "print(json.dumps({\"api_key\": (k[:10] + \"***len\" + str(len(k))) if k else k, \"base_url\": r.get(\"base_url\")}, ensure_ascii=False))\n"
)
env = {"PATH": "/usr/bin:/bin", "HOME": "/home/ubuntu", "HERMES_HOME": HOMES[0]}
try:
    for line in open(HOMES[0] + "/.env"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            a, _, b = line.partition("=")
            env[a.strip()] = b.strip()
except Exception: pass
env["OPENAI_API_KEY"] = EK
r = subprocess.run([VPY, "-c", code], env=env, cwd=REPO, capture_output=True, text=True, timeout=90)
print("  硬覆盖复审:", (r.stdout or "").strip()[:300])

print("==H 重启 ==")
subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT30_DONE 看G段: gsk开头=钥匙通道已通,去TG发消息; B/C/D/E命中数全贴回来")
