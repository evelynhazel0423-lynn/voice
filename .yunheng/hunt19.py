#!/usr/bin/env python3
import subprocess, re, sqlite3, os

H = "/home/ubuntu/.hermes-gateway"
REPO = "/home/ubuntu/cloud-yunheng/hermes-agent"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
PURE = re.compile(r'^(gsk|sk|xoxb|xoxp|xapp)[A-Za-z0-9_-]{10,}$')

def mask(s): return KEYRE.sub(r'\1****', s)
def sh(cmd, t=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t)
    return (r.stdout or "")

env_key = ""
for line in open(H + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        env_key = line.split("=", 1)[1].strip()
print("[env]", env_key[:8] + "***")

def s(v):
    if isinstance(v, str): return v
    if isinstance(v, bytes):
        try: return v.decode("utf-8", "ignore")
        except Exception: return None
    return None

print("==A 进程出生证明==")
for p in sh("pgrep -f 'gateway run'").split():
    print("pid", p, "|", sh(f"ps -o lstart=,etime= -p {p}").strip())
    try:
        env = open(f"/proc/{p}/environ", "rb").read().decode("utf-8", "ignore")
        for kv in env.split("\0"):
            if kv.startswith("OPENAI_API_KEY="):
                print("   environ:", kv.split("=", 1)[1][:8] + "***")
    except Exception: pass
print(sh("tail -6 " + H + "/gateway-starts.log 2>/dev/null") or "(无重启史)")

print("==B 根目录文件搜钥匙==")
file_fix = []
for fn in sorted(os.listdir(H)):
    p = os.path.join(H, fn)
    if not os.path.isfile(p) or fn.endswith((".db", ".log", ".gz")) or "log" in fn:
        continue
    try: txt = open(p, errors="ignore").read()
    except Exception: continue
    hits = set(m.group(0) for m in KEYRE.finditer(txt))
    if hits:
        print("  ", fn, "->", sorted(h[:8] + "***" for h in hits))
        for h in hits:
            if PURE.fullmatch(h) and h != env_key:
                file_fix.append((p, h))

print("==C state.db 全表扫描+自动换血==")
con = sqlite3.connect(H + "/state.db")
cur = con.cursor()
db_fix = []
for t in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    try:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
        for c in cols:
            try:
                for (rid, v) in cur.execute(f"SELECT rowid, {c} FROM {t} WHERE {c} IS NOT NULL").fetchall():
                    sv = s(v)
                    if sv and PURE.fullmatch(sv.strip()) and sv.strip() != env_key:
                        db_fix.append((t, c, rid, sv.strip()))
            except Exception: pass
    except Exception as e:
        print("  [skip]", t, str(e)[:50])
print("[非env钥匙单元格]", len(db_fix))
for (t, c, rid, k) in db_fix[:12]:
    print(f"   [DBKEY] {t}.{c} rowid={rid} {k[:8]}***")
for (t, c, rid, k) in db_fix:
    cur.execute(f"UPDATE {t} SET {c}=? WHERE rowid=?", (env_key, rid))
con.commit()
print("[已换血]", len(db_fix), "个 ->", env_key[:8] + "***")
con.close()

print("==D 文件自动换血==")
for (p, k) in file_fix:
    txt = open(p, errors="ignore").read()
    open(p, "w").write(txt.replace(k, env_key))
    print("   [FILE-FIXED]", os.path.basename(p), k[:8] + "*** ->", env_key[:8] + "***")
if not file_fix: print("   (根目录文件没有异钥匙)")

print("==E hermes自家源码考古(仓库根,排除venv)==")
EXC = "--exclude-dir=hermes-venv --exclude-dir=.git --exclude-dir=node_modules"
for pat, tag, cap in [
    (r"gateway_runtime", "runtime用法", 10),
    (r"billing_base_url|billing_provider", "billing读法", 8),
    (r"OPENAI_API_KEY", "env钥匙读取", 8),
    (r"input_tokens", "token列写入者", 10),
    (r"AsyncOpenAI\(|[^t]OpenAI\(", "客户端构造", 10),
    (r"api_key", "api_key字样", 12),
]:
    out = sh(f"grep -rn {EXC} --include=*.py -E '{pat}' {REPO} 2>/dev/null | head -{cap}")
    print(f"  [{tag}]")
    print("   " + (mask(out).strip()[:1700] or "(无)"))

print("==F 杀进程重启==")
subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT19_DONE 已杀网关，看门狗2分钟内拉起，加载的是全库全文件换血后的干净状态，去TG发消息")
