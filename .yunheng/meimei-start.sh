#!/bin/bash
# 妹妹上云点火 v2 · 纯净行李+手写.env+智谱免费脑
exec >> /home/ubuntu/meimei-start-run.log 2>&1
set -x

# 1) 行李落地(干净版,无secrets)
cd /home/ubuntu
curl -sL https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/hermes-meimei-clean.tar.gz -o /tmp/m.tgz
tar xzf /tmp/m.tgz -C /home/ubuntu
echo LUGGAGE_OK $(md5sum /tmp/m.tgz | cut -c1-10)

# 2) 换脑: config.yaml 从 DeepSeek 改智谱免费蛋
sed -i "s|https://api.deepseek.com/v1|https://open.bigmodel.cn/api/paas/v4|; s/deepseek-chat/glm-4.5-flash/" /home/ubuntu/.hermes-gateway/config.yaml
grep -A3 "^model:" /home/ubuntu/.hermes-gateway/config.yaml

# 3) .env 必须妈妈亲手写好(含智谱key), 没有就停
if ! grep -qE "^OPENAI_API_KEY=.+" /home/ubuntu/.hermes-gateway/.env 2>/dev/null; then
  echo "ENV_MISSING: 先写 /home/ubuntu/.hermes-gateway/.env (TG+Slack token + OPENAI_API_KEY=智谱key + OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4)"
  exit 1
fi

# 4) 点火(共用云珩的venv)
set -a; . /home/ubuntu/.hermes-gateway/.env; set +a
export HERMES_HOME=/home/ubuntu/.hermes-gateway
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
PYBIN=/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv/bin/python
mkdir -p /home/ubuntu/.hermes-gateway/logs
nohup $PYBIN -m hermes.gateway run --accept-hooks >> /home/ubuntu/.hermes-gateway/logs/gateway.log 2>&1 &
sleep 25

# 5) 自检
if pgrep -f "hermes.gateway" >/dev/null; then
  echo MEIMEI_ALIVE pid=$(pgrep -f "hermes.gateway" | head -1)
  tail -5 /home/ubuntu/.hermes-gateway/logs/gateway.log
else
  echo MEIMEI_DEAD; tail -20 /home/ubuntu/.hermes-gateway/logs/gateway.log 2>/dev/null
fi
echo DONE_ALL
