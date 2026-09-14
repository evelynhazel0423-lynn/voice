#!/bin/bash
exec >> /home/ubuntu/meimei-fix-run.log 2>&1
set -x
H=/home/ubuntu/.hermes-gateway
cd $H

# 1) 排干所有凭证/路由缓存(保守: 只删缓存不删会话)
ls $H/cache/ 2>/dev/null
rm -rf $H/cache/auth* $H/cache/credential* $H/cache/provider* $H/auth.lock 2>/dev/null
find $H -maxdepth 2 -name "*.lock" -delete 2>/dev/null
echo CACHE_CLEARED

# 2) state.db三连验(会话门牌+凭证表)
python3 - <<PYEOF
import sqlite3
c = sqlite3.connect("/home/ubuntu/.hermes-gateway/state.db")
print([r[0] for r in c.execute("select name from sqlite_master where type=\"table\"")])
for r in c.execute("select id, model, billing_base_url from sessions where ended_at is null limit 3"): print(r)
try:
    for t in ["provider_credentials","credentials","auth"]:
        try:
            n = c.execute(f"select count(*) from {t}").fetchone()[0]
            print(t, "rows:", n)
            for r in c.execute(f"select * from {t} limit 3"): print("  ", str(r)[:110])
        except Exception as e: print(t, "->", e)
except: pass
PYEOF

# 3) 杀净重启(带显式key)
pkill -9 -f "gateway run" 2>/dev/null; sleep 3
export HERMES_HOME=$H
set -a; . $H/.env; set +a
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
setsid nohup /home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv/bin/hermes gateway run --accept-hooks >> $H/logs/gateway.log 2>&1 < /dev/null &
disown
sleep 28
pgrep -f "gateway run" >/dev/null && echo FIX_ALIVE pid=$(pgrep -f "gateway run"|head -1) || echo FIX_DEAD
tail -3 $H/logs/gateway.log
echo FIX_DONE
