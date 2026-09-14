#!/usr/bin/env python3
import sqlite3, re, json, subprocess

H = "/home/ubuntu/.hermes-gateway"
DB = H + "/state.db"

env_key = ""
for line in open(H + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        env_key = line.split("=", 1)[1].strip()
PURE = re.compile(r'^(gsk|sk|xoxb|xoxp|xapp)[A-Za-z0-9_-]{10,}$')

def s(v):
    if isinstance(v, str): return v
    if isinstance(v, bytes): return v.decode("utf-8", "ignore")
    return None

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
live = [r[0] for r in cur.execute("SELECT id FROM sessions WHERE ended_at IS NULL")]
print("[live sessions]", len(live))
if not live:
    print("没有活跃会话?!")
    raise SystemExit
qm = ",".join("?" * len(live))

# 1) 换钥匙：活跃会话所有列里“整串就是旧钥匙”的单元格 -> env新钥匙
cols = [r[1] for r in cur.execute("PRAGMA table_info(sessions)")]
replaced = 0
for c in cols:
    try:
        rows = cur.execute(f"SELECT rowid, {c} FROM sessions WHERE id IN ({qm}) AND {c} IS NOT NULL", live).fetchall()
    except Exception:
        continue
    for r in rows:
        v = s(r[1])
        if v and PURE.fullmatch(v.strip()) and v.strip() != env_key:
            cur.execute(f"UPDATE sessions SET {c}=? WHERE rowid=?", (env_key, r[0]))
            replaced += 1
            print("[REKEY] 列:", c)
con.commit()
print("[换掉的钥匙单元格]", replaced)

# 2) 拆雷：model_config.gateway_runtime.base_url 指向非groq的 -> groq
fixed = 0
for r in cur.execute(f"SELECT rowid, model_config FROM sessions WHERE id IN ({qm}) AND model_config IS NOT NULL", live).fetchall():
    v = s(r[1])
    if not v: continue
    try:
        mc = json.loads(v)
    except Exception:
        continue
    gr = mc.get("gateway_runtime") if isinstance(mc, dict) else None
    if isinstance(gr, dict) and gr.get("base_url") and "groq" not in gr["base_url"]:
        old = gr["base_url"]
        gr["base_url"] = "https://api.groq.com/openai/v1"
        mc["gateway_runtime"] = gr
        cur.execute("UPDATE sessions SET model_config=? WHERE rowid=?", (json.dumps(mc, ensure_ascii=False), r[0]))
        fixed += 1
        print("[REBASE]", old[:40], "-> groq")
con.commit()
print("[拆掉的deepseek雷]", fixed)

# 3) 其他表里有纯钥匙的：只报告不动
for t in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    if t == "sessions": continue
    try:
        tcols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
        for c in tcols:
            for rr in cur.execute(f"SELECT rowid, {c} FROM {t} WHERE {c} IS NOT NULL").fetchall():
                v = s(rr[1])
                if v and PURE.fullmatch(v.strip()):
                    print(f"[库内其他钥匙] {t}.{c} rowid={rr[0]}", "SAME" if v.strip() == env_key else "DIFFERENT")
    except Exception:
        pass
con.close()

# 4) 终验：活跃行里不该再有 != env_key 的钥匙
con = sqlite3.connect(DB)
bad = 0
for c in cols:
    try:
        for r in con.execute(f"SELECT {c} FROM sessions WHERE ended_at IS NULL AND {c} IS NOT NULL"):
            v = s(r[0])
            if v and PURE.fullmatch(v.strip()) and v.strip() != env_key:
                bad += 1
    except Exception:
        pass
print("[终验: 活跃行残余异钥匙]", bad)
con.close()

# 5) 杀进程让看门狗拉起（内存里的旧会话快照一并清掉）
subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT17_DONE 已杀网关，等看门狗2分钟内拉起，然后TG发消息")
