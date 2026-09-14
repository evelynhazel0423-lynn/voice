#!/usr/bin/env python3
import sqlite3, re, os, subprocess

DB = "/home/ubuntu/.hermes-gateway/state.db"
HOME = "/home/ubuntu/.hermes-gateway"
ENV = HOME + "/.env"

KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{16,}')
PUREKEY = re.compile(r'^(gsk|sk|xoxb|xoxp|xapp)[A-Za-z0-9_-]{10,}$')

def mask(v): return v[:10] + "***len=" + str(len(v))

env_key = ""
for line in open(ENV):
    if line.startswith("OPENAI_API_KEY="):
        env_key = line.strip().split("=", 1)[1].strip()
print("[env key]", mask(env_key))

def as_str(v):
    if isinstance(v, bytes):
        try: return v.decode("utf-8", "ignore")
        except Exception: return None
    return v if isinstance(v, str) else None

def keymatch(v):
    s = as_str(v)
    if not s or len(s) < 16 or len(s) > 8192: return None
    m = KEYRE.search(s)
    return m.group(0) if m else None

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("[tables]", tables)

live_ids = [r[0] for r in cur.execute("SELECT id FROM sessions WHERE ended_at IS NULL")]
print("[live sessions]", len(live_ids))

hits = {}  # (table,col) -> list of (rowid, matched, pure?)
for t in tables:
    try:
        rows = cur.execute(f"SELECT rowid, * FROM {t}").fetchall()
    except Exception as e:
        print("[skip table]", t, e); continue
    if not rows: continue
    cols = rows[0].keys()
    for c in cols:
        if c == "rowid": continue
        found = []
        for r in rows:
            m = keymatch(r[c])
            if m:
                pure = bool(PUREKEY.fullmatch(as_str(r[c]).strip()))
                found.append((r["rowid"], m, pure))
        if found:
            hits[(t, c)] = found
            fps = sorted(set(mask(m) for _, m, _ in found))
            npure = sum(1 for _, _, p in found if p)
            print(f"[HIT] {t}.{c} rows={len(found)} pure={npure} -> {fps}")

if not hits:
    print("[NO KEY-LIKE VALUES IN DB] -- 库里没有钥匙，凶手在库外")

# ---- 修复：sessions 活跃行 & 疑似凭据表，纯钥匙值换成 env_key ----
changed = 0
for (t, c), found in hits.items():
    if t == "sessions":
        for (rowid, m, pure) in found:
            if pure and m != env_key:
                cur.execute(f"UPDATE sessions SET {c}=? WHERE rowid=?", (env_key, rowid))
                changed += 1
    elif re.search(r"provider|credential|auth|secret", t, re.I):
        for (rowid, m, pure) in found:
            if pure and m != env_key:
                cur.execute(f"UPDATE {t} SET {c}=? WHERE rowid=?", (env_key, rowid))
                changed += 1
                print(f"[REKEY] {t}.{c} rowid={rowid} {mask(m)} -> gsk_K13p…")
    else:
        for (rowid, m, pure) in found:
            if not pure:
                s = as_str(cur.execute(f"SELECT {c} FROM {t} WHERE rowid=?", (rowid,)).fetchone()[0])
                i = s.find(m)
                ctx = s[max(0, i-40):i+len(m)+10]
                print(f"[EMBEDDED-ONLY-REPORT] {t}.{c} rowid={rowid} ctx={mask(ctx)}")
con.commit()
print("[rekeyed rows]", changed)

# 复查 sessions 活跃行
for (t, c) in hits:
    if t == "sessions":
        for r in cur.execute(f"SELECT id, {c} FROM sessions WHERE ended_at IS NULL"):
            v = as_str(r[1]) or ""
            print("[after]", r[0][:24], mask(v) if v else "(empty)")
con.close()

# ---- 活跃会话 billing 三字段复查 ----
con = sqlite3.connect(DB)
for r in con.execute("SELECT id, model, billing_provider, billing_base_url FROM sessions WHERE ended_at IS NULL"):
    print("[billing]", r[0][:24], r[1], r[2], r[3])
con.close()

# ---- 库外文件搜查 ----
print("== FILE GREP ==")
try:
    out = subprocess.run(
        ["grep", "-rInE", r"(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{16,}", HOME,
         "--exclude-dir=logs", "--exclude-dir=audio_cache"],
        capture_output=True, text=True, timeout=60).stdout
    for line in out.splitlines():
        masked = re.sub(r"(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*", r"\1****", line)
        print(masked[:160])
    if not out.strip(): print("(库外文件无钥匙)")
except Exception as e:
    print("grep err:", e)
print("HUNT15_DONE")
