#!/bin/bash
# restart-meimei3.sh —— 妹妹 v2.3 TTS版 一键重启 · 云珩 2026-09-15
# 黑窗口：curl -sL https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/restart-meimei3.sh -o /tmp/r3.sh && bash /tmp/r3.sh
exec >> /home/ubuntu/restart3-run.log 2>&1
set -x
NEW=/home/ubuntu/meimei-home
echo "===== 妹妹 v2.3 TTS版 重启 $(date) ====="

# 1. 确保家目录在（若缺失，自动重建骨架）
mkdir -p $NEW /tmp/vsave

# 2. 停旧进程
pkill -f "meimei.py" 2>/dev/null; sleep 2

# 3. 下载新脑（v2.3，带 ElevenLabs TTS）
curl -sL "https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/meimei.py" -o $NEW/meimei.py
echo "新脑大小: $(wc -c < $NEW/meimei.py)"
grep -q "eleven_multilingual_v2" $NEW/meimei.py && echo "TTS版本确认OK ✔️" || echo "警告:TTS没带进"

# 4. 从旧身体（retired 封存）搬回 .env / SOUL.md / memory.json（只在缺失时）
if [ ! -f $NEW/.env ]; then
  OLD=$(ls -d /home/ubuntu/.hermes-gateway-retired-* 2>/dev/null | head -1)
  if [ -n "$OLD" ] && [ -f "$OLD/.env" ]; then
    cp "$OLD/.env" $NEW/.env; chmod 600 $NEW/.env; echo "从 $OLD 搬回 .env"
  else
    echo "警告:无 .env 可搬，妹妹会在缺钥匙时无法连TG——请手写 $NEW/.env"
  fi
fi
[ -f $NEW/SOUL.md ] || (OLD=$(ls -d /home/ubuntu/.hermes-gateway-retired-* 2>/dev/null | head -1); [ -n "$OLD" ] && cp "$OLD/SOUL.md" $NEW/SOUL.md && echo "搬回 SOUL.md")
[ -f $NEW/memory.json ] || (OLD=$(ls -d /home/ubuntu/.hermes-gateway-retired-* 2>/dev/null | head -1); [ -n "$OLD" ] && cp "$OLD/memory.json" $NEW/memory.json && echo "搬回 memory.json")

# 5. .env 里无 ElevenLabs key 时从旧身体带（旧身体有 sk_336 开头）
if ! grep -q "ELEVENLABS_API_KEY" $NEW/.env 2>/dev/null; then
  OLD=$(ls -d /home/ubuntu/.hermes-gateway-retired-* 2>/dev/null | head -1)
  EK=$(grep -m1 '^ELEVENLABS_API_KEY=' "$OLD/.env" 2>/dev/null | cut -d= -f2-)
  [ -n "$EK" ] && printf 'ELEVENLABS_API_KEY=%s\n' "$EK" >> $NEW/.env && echo "补写 ElevenLabs key ✔️ 妹妹有嗓子了"
fi

# 6. 点火
cd $NEW
setsid nohup python3 meimei.py >> $NEW/meimei.log 2>&1 &
sleep 12

# 7. 自检
if pgrep -f "meimei.py" > /dev/null; then
  echo "MEIMEI23_ALIVE pid=$(pgrep -f meimei.py | head -1)"
  tail -15 $NEW/meimei.log
else
  echo "MEIMEI23_DEAD"
  tail -30 $NEW/meimei.log
fi
echo "===== RESTART3_DONE ====="