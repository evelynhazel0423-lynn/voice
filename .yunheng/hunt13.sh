echo "==0 目录=="
ls -la /home/ubuntu/.hermes-gateway/ 2>/dev/null | head -20
echo "==A config.yaml(密已打码)=="
sed -E 's/((gsk_|sk-|xoxb-|xoxp-|xapp-1-A).{4}).*/\1***/' /home/ubuntu/.hermes-gateway/config.yaml 2>/dev/null
echo "==B gateway进程+environ=="
ps aux | grep -iE 'hermes|gateway' | grep -v grep | head -4 | cut -c1-110
for p in $(pgrep -f hermes); do echo "-- pid=$p environ:"; tr '\0' '\n' </proc/$p/environ 2>/dev/null | grep -E '^OPENAI_(API_KEY|BASE_URL)=' | sed -E 's/(=.{10}).*/\1***/'; done
echo "==C .env的key指纹=="
grep -E '^OPENAI_API_KEY=' /home/ubuntu/.hermes-gateway/.env | sed -E 's/(=.{10}).*/\1***/'
echo "==D state.db表=="
sqlite3 /home/ubuntu/.hermes-gateway/state.db '.tables'
echo "==E sessions列=="
sqlite3 /home/ubuntu/.hermes-gateway/state.db 'PRAGMA table_info(sessions);' | cut -d'|' -f2 | tr '\n' ' '; echo
echo "==F 活跃会话billing=="
sqlite3 /home/ubuntu/.hermes-gateway/state.db "SELECT id, model, billing_provider, billing_base_url FROM sessions WHERE ended_at IS NULL LIMIT 4;"
echo "==G key类列指纹=="
for col in $(sqlite3 /home/ubuntu/.hermes-gateway/state.db "PRAGMA table_info(sessions);" | cut -d'|' -f2 | grep -iE 'key|token|secret|cred'); do echo "-- col=$col"; sqlite3 /home/ubuntu/.hermes-gateway/state.db "SELECT id, substr(coalesce($col,''),1,8), length(coalesce($col,'')) FROM sessions WHERE ended_at IS NULL LIMIT 5;"; done
echo "==H 401现场=="
for f in $(find /home/ubuntu -maxdepth 3 -name '*.log' 2>/dev/null | head -14); do grep -qiE '401|invalid api' "$f" 2>/dev/null && { echo "-- $f"; grep -iE '401|invalid api' "$f" | tail -4; }; done
echo "==I 最新log尾=="
last=$(find /home/ubuntu -maxdepth 3 -name '*.log' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
echo "log=$last"; tail -8 "$last" 2>/dev/null
echo "==J 看门狗+cron=="
head -30 /home/ubuntu/meimei-watchdog.sh 2>/dev/null
crontab -l 2>/dev/null | grep -iE 'meimei|hermes'
