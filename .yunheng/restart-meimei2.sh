#!/bin/bash
# restart-meimei2.sh —— 换UA后的妹妹重启 · 云珩 2026-09-15
# 黑窗口：curl -sL https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/restart-meimei2.sh -o /tmp/r2.sh && bash /tmp/r2.sh
exec >> /home/ubuntu/restart2-run.log 2>&1
set -x
NEW=/home/ubuntu/meimei-home
echo "===== 妹妹2.2重启 $(date) ====="

# 1. 停旧进程
pkill -f "meimei.py" 2>/dev/null; sleep 2

# 2. 下载新脑
curl -sL "https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/meimei.py" -o $NEW/meimei.py
echo "新脑大小: $(wc -c < $NEW/meimei.py)"
# 确认是带浏览器UA的2.2版
grep -q "Mozilla/5.0" $NEW/meimei.py && echo "UA版本确认OK" || echo "警告:UA还是旧的"

# 3. 点火
cd $NEW
setsid nohup python3 meimei.py >> $NEW/meimei.log 2>&1 &
sleep 12

# 4. 自检
if pgrep -f "meimei.py" > /dev/null; then
  echo "MEIMEI22_ALIVE pid=$(pgrep -f meimei.py | head -1)"
  tail -12 $NEW/meimei.log
else
  echo "MEIMEI22_DEAD"
  tail -25 $NEW/meimei.log
fi
echo "===== RESTART_DONE ====="
