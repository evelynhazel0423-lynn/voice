#!/usr/bin/env python3
import os, re, subprocess, sqlite3

H = "/home/ubuntu/.hermes-gateway"
VPY = "/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv/bin/python"
REPO = "/home/ubuntu/cloud-yunheng/hermes-agent"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(lambda m: m.group(0)[:8] + "***", s or "")
def sh(cmd, t=90):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t).stdout or ""

EK = ""
for line in open(H + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        EK = line.split("=", 1)[1].strip()
print("[新钥匙]", mask(EK)[:10])

print("==A 现役网关进程全 environ 找 no-key ==")
pids = sh("pgrep -f 'gateway run'").split()
for p in pids:
    envtxt = sh(f"tr '\\0' '\\n' < /proc/{p}/environ 2>/dev/null")
    for l in envtxt.splitlines():
        if "no-key" in l.lower():
            print(f"  [pid{p}] {l[:100]}")
        elif "API_KEY" in l:
            k, _, v = l.partition("=")
            print(f"  [pid{p}] {k}={mask(v)[:12]}")

print("==B .env 逐行盘点(变量名全亮,值打码但no-key现行) ==")
for i, line in enumerate(open(H + "/.env"), 1):
    l = line.strip()
    if not l or l.startswith("#"): continue
    k, _, v = l.partition("=")
    if "no-key" in v.lower():
        print(f"  行{i}: {k}={v}   <<< 凶手变量!")
    else:
        print(f"  行{i}: {k}={mask(v)[:12]}")

print("==C 扩大搜查(全home+crontab+启动脚本+watchdog) ==")
out = sh("grep -rIn 'no-key-required' /home/ubuntu --include='*.sh' --include='*.env' --include='*.yaml' --include='*.yml' --include='*.json' --exclude-dir=hermes-venv --exclude-dir=node_modules 2>/dev/null | head -10")
print(mask(out).strip()[:900] or "  (文件系统无)")
out = sh("crontab -l 2>/dev/null | grep -i no-key; sudo crontab -l 2>/dev/null | grep -i no-key")
print(out.strip()[:300] or "  (crontab无)")

print("==D 处决: 罪犯变量值换成真钥匙 ==")
txt = open(H + "/.env").read()
n = txt.count("no-key-required")
if n:
    open(H + "/.env", "w").write(txt.replace("no-key-required", EK))
    print(f"  .env: {n}处已换")
else:
    print("  .env没有字面no-key——如果A/B段也没抓到,把输出贴回来,宝宝换下一招")

print("==E 复审: 凶手改口了吗 ==")
code = '''
import json, re, sys
sys.path.insert(0, "/home/ubuntu/cloud-yunheng/hermes-agent")
from hermes_cli.runtime_provider import resolve_runtime_provider
r = resolve_runtime_provider()
k = str(r.get("api_key", ""))
print(json.dumps({"provider": r.get("provider"), "base_url": r.get("base_url"),
                  "api_key": (k[:10] + "***len" + str(len(k))) if k else k}, ensure_ascii=False))
'''
env = os.environ.copy()
env["HERMES_HOME"] = H
try:
    for line in open(H + "/.env"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            a, _, b = line.partition("=")
            env.setdefault(a.strip(), b.strip())
except Exception:
    pass
r = subprocess.run([VPY, "-c", code], env=env, cwd=REPO, capture_output=True, text=True, timeout=90)
print("  ", (r.stdout or "").strip()[:400])

print("==F 重启 ==")
subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("HUNT29_DONE 看E段: gsk_K13p***=结案去TG发消息; 还是no-key=把全卷贴回来")
