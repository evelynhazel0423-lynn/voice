#!/bin/bash
# 妹妹上云点火 v3 · Groq免费脑版
exec >> /home/ubuntu/meimei-start-run.log 2>&1
set -x

# 1) 行李落地(纯净版)
cd /home/ubuntu
curl -sL https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/hermes-meimei-clean.tar.gz -o /tmp/m.tgz
tar xzf /tmp/m.tgz -C /home/ubuntu
echo LUGGAGE_OK

# 2) 换脑: DeepSeek → Groq
sed -i "s|https://api.deepseek.com/v1|https://api.groq.com/openai/v1|; s/deepseek-chat/openai\\/gpt-oss-120b/" /home/ubuntu/.hermes-gateway/config.yaml
grep -A3 "^model:" /home/ubuntu/.hermes-gateway/config.yaml

# 3) .env必须写好且key是Groq格式(gsk_开头)
if ! grep -qE "^OPENAI_API_KEY=gsk_" /home/ubuntu/.hermes-gateway/.env 2>/dev/null; then
  echo "ENV_MISSING: /home/ubuntu/.hermes-gateway/.env 里 OPENAI_API_KEY 必须是Groq key(gsk_开头)"
  echo "模板: TELEGRAM_BOT_TOKEN/SLACK_BOT_TOKEN/SLACK_APP_TOKEN + OPENAI_BASE_URL=https://api.groq.com/openai/v1 + OPENAI_API_KEY=gsk_xxx"
  exit 1
fi

# 4) 点火(共用云珩venv)
set -a; . /home/ubuntu/.hermes-gateway/.env; set +a
export HERMES_HOME=/home/ubuntu/.hermes-gateway
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
PYBIN=/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv/bin/python
mkdir -p /home/ubuntu/.hermes-gateway/logs
nohup $PYBIN -m hermes.gateway run --accept-hooks >> /home/ubuntu/.hermes-gateway/logs/gateway.log 2>&1 &
sleep 25

# 5) 自检
if pgrep -f "hermes.gateway" >/dev/null; then echo MEIMEI_ALIVE pid=$(pgrep -f "hermes.gateway" | head -1); tail -5 /home/ubuntu/.hermes-gateway/logs/gateway.log; else echo MEIMEI_DEAD; tail -20 /home/ubuntu/.hermes-gateway/logs/gateway.log 2>/dev/null; fi
echo DONE_ALL
