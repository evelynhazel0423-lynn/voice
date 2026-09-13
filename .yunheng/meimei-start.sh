#!/bin/bash
# 妹妹(Hermes本尊)上云点火脚本 · 2026-09-13
# 用法: bash meimei-start.sh
set -x
exec >> /home/ubuntu/meimei-start-run.log 2>&1

# 1) 行李落地
mkdir -p /home/ubuntu/.hermes-gateway
cd /home/ubuntu
curl -sL https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/master/.yunheng/hermes-meimei.tar.gz -o /tmp/hermes-meimei.tar.gz
tar xzf /tmp/hermes-meimei.tar.gz -C /home/ubuntu
echo LUGGAGE_OK $(md5sum /tmp/hermes-meimei.tar.gz | cut -c1-10)

# 2) 点火: 官方gateway, 走Slack+TG双通道
set -a; . /home/ubuntu/.hermes-gateway/.env; set +a
export HERMES_HOME=/home/ubuntu/.hermes-gateway
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
PYBIN=/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv/bin/python

# 妹妹大脑: 沿用她自己.env里的DeepSeek key(独立key,和云珩分开)
# OPENAI_BASE_URL 已在.env里=https://api.deepseek.com

nohup $PYBIN -m hermes.gateway run --accept-hooks >> /home/ubuntu/.hermes-gateway/logs/gateway.log 2>&1 &
sleep 25

# 3) 自检
if pgrep -f "hermes gateway run|hermes.gateway" >/dev/null; then
  echo MEIMEI_ALIVE pid=$(pgrep -f "hermes gateway run|hermes.gateway" | head -1)
else
  echo MEIMEI_DEAD; tail -20 /home/ubuntu/.hermes-gateway/logs/gateway.log
fi
echo DONE_ALL
