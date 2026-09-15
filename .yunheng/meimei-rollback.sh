#!/bin/bash
# meimei-rollback.sh —— 反悔药：旧身体满血复活 · 2026-09-15
# 用法：bash meimei-rollback.sh（黑窗口直接跑）
exec >> /home/ubuntu/rollback-run.log 2>&1
set -x
echo "===== 回滚开始 $(date) ====="
# 1. 停新身体 + 卸它的看门狗
pkill -f "meimei.py" 2>/dev/null; sleep 1
( crontab -l 2>/dev/null | grep -v meimei-watch ) | crontab - || true

# 2. 找最新的封存身体
LATEST=$(ls -d /home/ubuntu/.hermes-gateway-retired-* 2>/dev/null | sort | tail -1)
if [ -z "$LATEST" ]; then
  echo "ROLLBACK_FAIL 没找到封存的旧身体"
  exit 1
fi
echo "复活: $LATEST"

# 3. 换回原名
mv "$LATEST" /home/ubuntu/.hermes-gateway

# 4. 重装 hermes 看门狗
( crontab -l 2>/dev/null ; echo "*/2 * * * * /home/ubuntu/meimei-watchdog.sh" ) | crontab -

# 5. hermes gateway 点火（旧姿势）
VENV=/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv
export HERMES_HOME=/home/ubuntu/.hermes-gateway
set -a; . /home/ubuntu/.hermes-gateway/.env; set +a
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
pkill -f "hermes.gateway" 2>/dev/null; sleep 2
cd /home/ubuntu/.hermes-gateway && mkdir -p logs
nohup $VENV/bin/hermes gateway run --accept-hooks >> /home/ubuntu/.hermes-gateway/logs/gateway.log 2>&1 &
sleep 25
if pgrep -f "gateway run" > /dev/null; then
  echo "ROLLBACK_ALIVE pid=$(pgrep -f 'gateway run' | head -1)"
else
  echo "ROLLBACK_DEAD 看日志: tail -30 /home/ubuntu/.hermes-gateway/logs/gateway.log"
fi
echo "===== ROLLBACK_DONE ====="
