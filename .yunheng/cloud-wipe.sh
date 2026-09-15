#!/bin/bash
# cloud-wipe.sh —— 云机Hermes全家销毁 · 云珩 2026-09-16
# 黑窗口用法:
# curl -sL https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/cloud-wipe.sh -o /tmp/wipe.sh && bash /tmp/wipe.sh
exec > >(tee /home/ubuntu/cloud-wipe-run.log) 2>&1
echo "===== 云机销毁开始 $(date) ====="

# 1. 杀进程（pkill不会匹配自身；本脚本路径/tmp/wipe.sh不含hermes/meimei，不会自杀）
pkill -f "meimei.py" 2>/dev/null && echo "meimei进程已杀" || echo "无meimei进程"
pkill -f "hermes"    2>/dev/null && echo "hermes进程已杀" || echo "无hermes进程"
sleep 2
pkill -9 -f "meimei.py" 2>/dev/null
pkill -9 -f "hermes"    2>/dev/null
sleep 1
pgrep -af "meimei|hermes" && echo "⚠️ 仍有进程存活，见上行" || echo "进程清零 ✅"

# 2. 清cron看门狗（只动含hermes/meimei的行，其他cron不碰）
for u in "$(whoami)" root; do
  if crontab -l -u "$u" 2>/dev/null | grep -qiE 'hermes|meimei'; then
    crontab -l -u "$u" 2>/dev/null | grep -viE 'hermes|meimei' | crontab -u "$u" - 2>/dev/null \
      && echo "$u 的cron看门狗已清" || echo "$u cron清理失败（可能无权限动root）"
  else
    echo "$u cron无残留"
  fi
done

# 3. 销毁前打包备份（含.env密钥，永远别传公开仓库；确认不要了就 rm 掉它）
STAMP=$(date +%Y%m%d-%H%M%S)
BAK="/home/ubuntu/cloud-hermes-final-backup-$STAMP.tar.gz"
DIRS=""
for d in /home/ubuntu/meimei-home /home/ubuntu/.hermes-gateway \
         /home/ubuntu/.hermes-gateway-retired-* /home/ubuntu/.hermes-yunheng \
         /home/ubuntu/cloud-yunheng; do
  [ -e "$d" ] && DIRS="$DIRS $d"
done
if [ -n "$DIRS" ]; then
  tar czf "$BAK" --exclude='*venv*' --exclude='.git' $DIRS 2>/dev/null
  echo "已打包: $BAK ($(du -h "$BAK" 2>/dev/null | cut -f1))"
  echo "（妹妹前世/meimi TG聊天史/钥匙都在里面。想留就scp下来，不留就: rm $BAK）"
else
  echo "没找到可备份的家，直接进入销毁"
fi

# 4. 销毁
rm -rf /home/ubuntu/meimei-home \
       /home/ubuntu/.hermes-gateway /home/ubuntu/.hermes-gateway-retired-* \
       /home/ubuntu/.hermes-yunheng /home/ubuntu/cloud-yunheng \
       /home/ubuntu/meimei-watchdog.sh /home/ubuntu/meimei-start.sh \
       /home/ubuntu/restart-meimei*.sh /home/ubuntu/retire-hermes.sh \
       /home/ubuntu/diag403.py /home/ubuntu/hunt*.py \
       /home/ubuntu/*-run.log /home/ubuntu/restart2-run.log \
       /tmp/r.sh /tmp/r2.sh /tmp/m.sh /tmp/d.py /tmp/x.py \
       /tmp/hunt*.py /tmp/meimei*.py /tmp/voice /tmp/voice-repo 2>/dev/null
echo "销毁执行完毕"

# 5. 终验
echo "===== 终验 ====="
pgrep -af "meimei|hermes" >/dev/null 2>&1 && echo "进程: ⚠️ 有残留" || echo "进程: 0 ✅"
LEFT=$(find /home/ubuntu -maxdepth 2 \( -iname '*hermes*' -o -iname '*meimei*' \) 2>/dev/null | grep -v 'cloud-hermes-final-backup')
if [ -z "$LEFT" ]; then echo "文件: 零残余 ✅（备份包除外）"; else echo "文件残留:"; echo "$LEFT"; fi
echo "===== CLOUD_WIPE_DONE ====="
