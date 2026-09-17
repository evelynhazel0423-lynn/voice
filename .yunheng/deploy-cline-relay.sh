#!/bin/bash
# Cline 中继代理 · 云机一键部署（Mommy 黑窗口跑这一条就行）
# 完成后 Minis app 通过 http://18.138.236.82:8899/v1 接入 Cline 全量模型
set -e
DIR=/home/ubuntu/cline-relay
mkdir -p $DIR && cd $DIR

echo "== 1. 写 refreshToken =="
cat > refresh-token.txt << 'RT'
lTwsBaONhkDF6e9nRIPoV9Q1M
RT

echo "== 2. 下载代理 =="
for i in 1 2 3; do
  if curl -sL --max-time 20 https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/proxy-cloud.py -o proxy-cloud.py; then
    break
  fi
  sleep 3
done
[ -s proxy-cloud.py ] && echo "代理下载 OK $(wc -l < proxy-cloud.py) 行" || { echo "代理下载失败"; exit 1; }

echo "== 3. 停旧 + 点火 =="
pkill -f 'proxy-cloud.py' 2>/dev/null || true
nohup python3 $DIR/proxy-cloud.py 8899 > $DIR/relay.log 2>&1 &
sleep 5

echo "== 4. 自验 =="
curl -s --max-time 8 -o /dev/null -w "本地 /v1/models → %{http_code}\n" http://127.0.0.1:8899/v1/models
curl -s --max-time 15 http://127.0.0.1:8899/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"stealth/union-alpha","messages":[{"role":"user","content":"Reply with exactly: cloud-relay-ok"}],"max_tokens":20}' \
  | head -c 300
echo
echo "== 5. 实弹完成标志 =="
echo "CLOUD-CLINE-RELAY-DONE"
echo "外网地址: http://18.138.236.82:8899/v1"
