#!/usr/bin/env python3
import sqlite3, os, re, subprocess

DB = "/home/ubuntu/.hermes-gateway/state.db"
ENV = "/home/ubuntu/.hermes-gateway/.env"

def mask(v):
    v = v or ""
    return (v[:8] + "***len=" + str(len(v))) if v else "(empty)"

# 1. 从 .env 拿新钥匙
env_key = ""
for line in open(ENV):
    if line.startswith("OPENAI_API_KEY="):
        env_key = line.strip().split("=", 1)[1]
print("[env key]", mask(env_key))

# 2. 开库，列出所有表和含 key/token/secret 的列
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("[tables]", tables)

key_cols = []  # (table, col)
for t in tables:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
    hits = [c for c in cols if re.search(r"api_key|apikey|token|secret|credential", c, re.I)]
    for c in hits:
        key_cols.append((t, c))
print("[key-ish columns]", key_cols)

# 3. 指纹亮相：谁的钥匙在库里躺着
live_ids = [r[0] for r in cur.execute("SELECT id FROM sessions WHERE ended_at IS NULL")]
print("[live sessions]", live_ids)
for (t, c) in key_cols:
    try:
        rows = cur.execute(f"SELECT rowid, {c} FROM {t}").fetchall()
        vals = set(mask(r[1]) for r in rows if r[1])
        print(f"[{t}.{c}] ->", vals)
    except Exception as e:
        print(f"[{t}.{c}] read err:", e)

# 4. 修复：只动 sessions 活跃行，key 列统一换成 .env 新钥匙
changed = 0
if live_ids:
    for (t, c) in key_cols:
        if t == "sessions":
            cur.execute(f"UPDATE sessions SET {c}=? WHERE id IN ({','.join('?'*len(live_ids))}) AND ({c} IS NULL OR {c}!=?)",
                        [env_key] + live_ids + [env_key])
            changed += cur.rowcount
con.commit()
print("[updated live-session rows]", changed)

# 5. 复查指纹
for (t, c) in key_cols:
    if t == "sessions":
        for r in cur.execute(f"SELECT id, {c} FROM sessions WHERE ended_at IS NULL"):
            print("[after]", r[0], mask(r[1]))
con.close()
print("DB_DONE")
