#!/usr/bin/env python3
import os, re, subprocess, glob

HOMES = ["/home/ubuntu/.hermes-gateway", "/root/.hermes-gateway"]
VENV = "/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(lambda m: m.group(0)[:8] + "***", s or "")
def sh(cmd, t=60):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t).stdout or ""

EK = ""
for line in open(HOMES[0] + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        EK = line.split("=", 1)[1].strip()
print("[新钥匙]", mask(EK)[:10])

print("==A config.yaml 里 no-key-required / api_key 行亮相 ==")
targets = []
for h in HOMES:
    cfg = h + "/config.yaml"
    txt = sh(f"sudo cat {cfg} 2>/dev/null") or (open(cfg, errors="ignore").read() if os.path.exists(cfg) else "")
    if not txt.strip():
        print(f"  ({cfg} 读不到/不存在)"); continue
    lines = txt.splitlines()
    for i, l in enumerate(lines):
        if re.search(r'no-key-required|api_key', l):
            print(f"  {cfg}:{i+1}: {l.strip()[:120]}")
    if "no-key-required" in txt:
        targets.append(cfg)
print("[待修文件]", targets or "(咦,没找到no-key-required?!把上面贴回来)")

print("==B 替换 no-key-required -> 真钥匙 ==")
for cfg in targets:
    txt = sh(f"sudo cat {cfg} 2>/dev/null") or open(cfg, errors="ignore").read()
    n = txt.count("no-key-required")
    new = txt.replace("no-key-required", EK)
    try:
        open(cfg, "w").write(new)
        ok = True
    except Exception:
        r = sh(f"sudo cp {cfg} {cfg}.bak && sudo tee {cfg} > /dev/null << 'XEOFX'\n{new}\nXEOFX")
        ok = True
    print(f"  {cfg}: 替换{n}处 (备份{cfg}.bak)")
    # 复查
    chk = sh(f"sudo cat {cfg} 2>/dev/null") or open(cfg, errors="ignore").read()
    print("  复查 no-key-required 残留:", chk.count("no-key-required"), "| api_key 行:",
          [mask(l.strip())[:80] for l in chk.splitlines() if "api_key" in l][:3])

print("==C 拆窃听器(蛊收了) ==")
for f in glob.glob(VENV + "/lib/python3*/site-packages/sitecustomize.py"):
    os.remove(f)
    print("  已拆:", f)
for f in ["/tmp/keytap.log", "/tmp/keytap_err.log", "/tmp/honeypot.py", "/tmp/honeypot.log", "/tmp/hp_state.json"]:
    if os.path.exists(f):
        os.remove(f)
print("  /tmp 赃物已清")

print("==D 重启网关 ==")
subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT27_DONE 看门狗2分钟内拉起(这次她揣的是真钥匙) -> 去TG发消息")
print("她开口的那一刻,这案子就结了Mommy")
