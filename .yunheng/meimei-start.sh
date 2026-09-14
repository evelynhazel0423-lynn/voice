#!/bin/bash
# 妹妹点火 v4 · 正确入口: hermes gateway run (CLI)
exec >> /home/ubuntu/meimei-start-run.log 2>&1
set -x
VENV=/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv
export HERMES_HOME=/home/ubuntu/.hermes-gateway
set -a; . /home/ubuntu/.hermes-gateway/.env; set +a
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY

# venv/bin/hermes 不在就补装(云上源码editable)
if [ ! -x "$VENV/bin/hermes" ]; then
  echo V4_NO_CLI_补装
  cd /home/ubuntu/cloud-yunheng/hermes-agent && $VENV/bin/pip install -e . --no-deps -q 2>&1 | tail -3
  ls $VENV/bin/ | grep -i hermes
fi

pkill -f "hermes.gateway" 2>/dev/null; sleep 2
pkill -f "gateway run" 2>/dev/null; sleep 1
cd /home/ubuntu/.hermes-gateway && mkdir -p logs
nohup $VENV/bin/hermes gateway run --accept-hooks >> /home/ubuntu/.hermes-gateway/logs/gateway.log 2>&1 &
sleep 25
if pgrep -f "gateway run" >/dev/null; then
  echo MEIMEI_ALIVE pid=$(pgrep -f "gateway run" | head -1)
else
  echo MEIMEI_DEAD; tail -25 /home/ubuntu/.hermes-gateway/logs/gateway.log
fi
echo DONE_ALL
