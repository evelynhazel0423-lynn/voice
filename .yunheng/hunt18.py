#!/usr/bin/env python3
import re, subprocess, sqlite3, os, glob

H = "/home/ubuntu/.hermes-gateway"
SP = "/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv/lib"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(r'\1****', s)

print("==A hunt17痕迹+活跃行token列现状==")
print("hunt17在/tmp:", os.path.exists("/tmp/hunt17.py"))
try:
    con = sqlite3.connect(H + "/state.db")
    cols = [r[1] for r in con.execute("PRAGMA table_info(sessions)")]
    for c in cols:
        try:
            vals = set()
            for r in con.execute(f"SELECT {c} FROM sessions WHERE ended_at IS NULL AND {c} IS NOT NULL"):
                v = r[0] if isinstance(r[0], str) else None
                if v and re.fullmatch(r'(gsk|sk|xoxb)[A-Za-z0-9_-]{10,}', v.strip()):
                    vals.add(v[:10] + "***")
            if vals:
                print(f"  列[{c}] 指纹:", sorted(vals))
        except Exception:
            pass
    con.close()
except Exception as e:
    print("db err:", e)

print("==B 最新401现场(判断新旧)==")
try:
    lines = open(H + "/logs/errors.log", errors='ignore').read().splitlines()
    hits = [l for l in lines if re.search(r'API call failed|provider=|base_url', l)]
    for l in hits[-6:]:
        print(mask(l)[:230])
except Exception as e:
    print("log err:", e)

print("==C 现役进程environ==")
out = subprocess.run(["pgrep", "-af", "gateway run"], capture_output=True, text=True).stdout
print(out.strip()[:150] or "(无网关进程!)")
for p in subprocess.run(["pgrep", "-f", "gateway run"], capture_output=True, text=True).stdout.split():
    try:
        env = open(f"/proc/{p}/environ", "rb").read().decode("utf-8", "ignore")
        for kv in env.split("\0"):
            if kv.startswith("OPENAI_API_KEY="):
                print(f"  pid{p} env key:", kv[:16] + "***")
    except Exception:
        pass

print("==D cache/channels/bin/gateway/cron 目录里找credential==")
for d in ["cache", "channels", "bin", "gateway", "cron"]:
    p = H + "/" + d
    if not os.path.isdir(p): continue
    out = subprocess.run(["grep", "-rInE", r"(gsk|sk|xoxb)-?[A-Za-z0-9_-]{20,}", p],
                         capture_output=True, text=True, timeout=30)
    n = len(out.stdout.splitlines())
    print(f"  {d}/: {'命中'+str(n)+'行' if n else '无钥匙'}")
    for line in out.stdout.splitlines()[:6]:
        print("   ", mask(line)[:170])

print("==E hermes源码:key从哪来(重点)==")
hits = []
for pydir in glob.glob(SP + "/python3.*/site-packages"):
    for pat, tag in [(r"OPENAI_API_KEY", "env读取"),
                     (r"input_tokens|output_tokens", "token列写入"),
                     (r"Authorization.{0,20}Bearer", "鉴权头"),
                     (r"def .{0,30}api_key|api_key\s*=", "api_key赋值")]:
        out = subprocess.run(["grep", "-rn", "-E", pat, pydir, "--include=*.py"],
                             capture_output=True, text=True, timeout=90)
        ls = [l for l in out.stdout.splitlines() if "/hermes" in l][:8]
        print(f"  [{tag}] {len(ls)}行:")
        for l in ls:
            print("   ", mask(l)[:230])
print("==F gateway_runtime相关: 源码里怎么用==")
for pydir in glob.glob(SP + "/python3.*/site-packages"):
    out = subprocess.run(["grep", "-rn", "-E", "gateway_runtime", pydir, "--include=*.py"],
                         capture_output=True, text=True, timeout=60)
    for l in out.stdout.splitlines()[:10]:
        print("   ", mask(l)[:230])
print("HUNT18_DONE")
