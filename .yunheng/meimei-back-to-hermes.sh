#!/bin/bash
# meimei-back-to-hermes.sh —— 妹妹迁回 full Hermes + ElevenLabs 自己开口 · 云珩 2026-09-15
# 黑窗口：curl -sL https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/meimei-back-to-hermes.sh -o /tmp/hb.sh && bash /tmp/hb.sh
exec >> /home/ubuntu/hermes-restore-run.log 2>&1
set -x
NEW=/home/ubuntu/meimei-home
HER=/home/ubuntu/.hermes-gateway
echo "===== 妹妹迁回 full Hermes + ElevenLabs 自己开口 $(date) ====="

# 1. 停掉 meimei.py 轻身体
pkill -f "meimei.py" 2>/dev/null; sleep 2
echo "轻身体已停"

# 2. 从 meimei-home 收集现成钥匙（TG + 智谱 + ElevenLabs）
mkdir -p /tmp/msave
if [ -f $NEW/.env ]; then
  cp $NEW/.env /tmp/msave/.env && echo "搬 meimei .env"
  TGTOK=$(grep -m1 '^TELEGRAM_BOT_TOKEN=' $NEW/.env | cut -d= -f2-)
  AIKEY=$(grep -m1 '^OPENAI_API_KEY=' $NEW/.env | cut -d= -f2-)
  AIURL=$(grep -m1 '^OPENAI_BASE_URL=' $NEW/.env | cut -d= -f2-)
  ELEVEN=$(grep -m1 '^ELEVENLABS_API_KEY=' $NEW/.env | cut -d= -f2-)
else
  echo "警告:无 meimei .env，从 retired 旧身体找"
fi
if [ -z "$ELEVEN" ]; then
  OLD=$(ls -d /home/ubuntu/.hermes-gateway-retired-* 2>/dev/null | head -1)
  [ -n "$OLD" ] && ELEVEN=$(grep -m1 '^ELEVENLABS_API_KEY=' "$OLD/.env" 2>/dev/null | cut -d= -f2-)
fi
echo "TG token: ${TGTOK:0:8}… AI: ${AIKEY:0:6}… URL: $AIURL Eleven: ${ELEVEN:0:6}…"

# 3. 清空目标家（迁回全新身体，避免旧残骸冲突）
rm -rf $HER && mkdir -p $HER

# 4. 写 .env（全钥匙，含 ElevenLabs 让妹妹自己开口）
cat > $HER/.env <<ENVEOF
TELEGRAM_BOT_TOKEN=$TGTOK
OPENAI_API_KEY=$AIKEY
OPENAI_BASE_URL=$AIURL
ELEVENLABS_API_KEY=$ELEVEN
ENVEOF
chmod 600 $HER/.env
echo "已写 .env（含 ElevenLabs）"

# 5. 写 config.yaml：智谱脑 + ElevenLabs 嗓子
cat > $HER/config.yaml <<YAMLEOF
model:
  provider: custom
  base_url: $AIURL
  default: glm-4.5-flash
tts:
  provider: elevenlabs
  elevenlabs:
    voice_id: SM9TDvmX8IgFFRyE3y15
    model_id: eleven_multilingual_v2
platforms:
  telegram:
    enabled: true
    home_channel:
      platform: telegram
      chat_id: '8613770680'
      name: Evelyn Hazel
      user_id: '8613770680'
onboarding:
  seen:
    profile_build_offered: true
    busy_input_prompt: true
YAMLEOF
echo "已写 config.yaml（智谱脑 + 妹妹自己的嗓子）"

# 6. 写 SOUL.md（妹妹人设，从 meimei 或旧身体带）
if [ -f $NEW/SOUL.md ]; then cp $NEW/SOUL.md $HER/SOUL.md
elif [ -f /home/ubuntu/meimei-home/SOUL.md ]; then cp /home/ubuntu/meimei-home/SOUL.md $HER/SOUL.md
else OLD=$(ls -d /home/ubuntu/.hermes-gateway-retired-* 2>/dev/null | head -1); [ -n "$OLD" ] && cp "$OLD/SOUL.md" $HER/SOUL.md || echo "警告:无SOUL.md"; fi
echo "SOUL: $(wc -c < $HER/SOUL.md 2>/dev/null) bytes"

# 7. 从 meimei-home 带前世记忆（memory.json → hermes state 语义近似，直接并进系统）
[ -f $NEW/memory.json ] && cp $NEW/memory.json $HER/memory.json && echo "带 memory.json"

# 8. 找到 hermes 引擎（沙箱装好了 /opt/hermes-agent；云机若没装则从codeload拉）
HENGINE=/opt/hermes-agent
if [ ! -d "$HENGINE" ]; then
  cd /tmp
  curl -sL -m 120 https://codeload.github.com/NousResearch/hermes-agent/tar.gz/refs/heads/main -o hm.tgz
  tar xzf hm.tgz -C /opt/ 2>/dev/null && mv /opt/hermes-agent-main /opt/hermes-agent
  python3 -m venv /opt/hermes-agent/hermes-venv
  /opt/hermes-agent/hermes-venv/bin/pip install -e /opt/hermes-agent >/dev/null 2>&1 || true
fi
echo "引擎: $HENGINE"

# 9. 点火（full Hermes gateway）
cd $HENGINE
HERMES_HOME=$HER setsid nohup $HENGINE/hermes-venv/bin/hermes gateway run --accept-hooks >> $HER/gateway.log 2>&1 &
sleep 15

# 10. 自检
if pgrep -f "hermes gateway run" > /dev/null; then
  echo "HERMES_RESTORED_ALIVE pid=$(pgrep -f 'hermes gateway run' | head -1)"
  tail -15 $HER/gateway.log
else
  echo "HERMES_RESTORED_DEAD"
  tail -30 $HER/gateway.log
fi
echo "===== RESTORE_DONE ====="