#!/usr/bin/env python3
# 用法: python3 hunt24.py arm   -> 装窃听器+重启网关, 然后去TG发消息
#       python3 hunt24.py read  -> 读窃听记录出判决
import sys, os, re, subprocess, sqlite3, json, glob, time

VENV = "/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv"
H = "/home/ubuntu/.hermes-gateway"
TAP = "/tmp/keytap.log"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(r'\1****', s or "")

def env_key():
    for line in open(H + "/.env"):
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""

mode = sys.argv[1] if len(sys.argv) > 1 else "arm"
EK = env_key()

if mode == "arm":
    # 1) 找 site-packages, 写 sitecustomize 窃听器
    sp = glob.glob(VENV + "/lib/python3*/site-packages")
    if not sp:
        print("没找到 site-packages!"); sys.exit(1)
    sp = sp[0]
    sc = os.path.join(sp, "sitecustomize.py")
    code = '''
# --- yunheng keytap (temporary debug) ---
try:
    import openai, json, datetime, os
    _orig_init = openai.OpenAI.__init__
    def _tap_init(self, *a, **kw):
        try:
            with open("/tmp/keytap.log", "a") as f:
                f.write(json.dumps({
                    "t": datetime.datetime.now().isoformat(),
                    "base_url": str(getattr(self, "base_url", "")),
                    "api_key": str(kw.get("api_key") or getattr(self, "api_key") or ""),
                    "args0": str(a[0]) if a else "",
                }) + "\\n")
        except Exception:
            pass
        return _orig_init(self, *a, **kw)
    openai.OpenAI.__init__ = _tap_init
except Exception:
    pass
# --- end keytap ---
'''
    open(sc, "w").write(code)
    print("[窃听器已植入]", sc)
    open(TAP, "w").close()

    # 2) errors.log 尾巴(看蜜罐期间有没有新401=Mommy到底发没发消息)
    print("== errors.log 最新5条 ==")
    try:
        lines = open(H + "/logs/errors.log", errors="ignore").read().splitlines()[-5:]
        for l in lines: print("  ", mask(l)[:200])
    except Exception as e:
        print("  ", e)

    # 3) 现役网关 environ 快照
    print("== 现役网关 environ 钥匙 ==")
    for p in subprocess.run(["pgrep", "-f", "gateway run"], capture_output=True, text=True).stdout.split():
        try:
            env = open(f"/proc/{p}/environ", "rb").read().decode("utf-8", "ignore")
            for kv in env.split("\0"):
                if kv.startswith("OPENAI_API_KEY="):
                    v = kv.split("=", 1)[1]
                    print(f"  pid{p}: {mask(v)[:10]} [{'OK=env同款' if v.strip()==EK else '***异***'}]")
        except Exception: pass

    # 4) 重启网关(带窃听器出生)
    subprocess.run(["pkill", "-9", "-f", "gateway run"])
    print("[网关已杀] 看门狗2分钟内拉起(带窃听器)")
    print("ARM_DONE 等2分钟 -> TG发一条 -> python3 /tmp/hunt24.py read")

elif mode == "read":
    print("== keytap.log ==")
    if os.path.exists(TAP):
        txt = open(TAP).read().strip()
        if not txt:
            print("  (空——她还没造过openai客户端。TG消息发了嘛?)")
        else:
            seen = set()
            for line in txt.splitlines():
                try: r = json.loads(line)
                except Exception: continue
                k = r.get("api_key", "")
                tag = "OK=env同款" if k.strip() == EK else ("***异钥匙***" if k else "(无key参数!)")
                print(f"  {r['t']} | base_url={r.get('base_url')} | key={mask(k)[:10]} [{tag}]")
                print(f"      args0={r.get('args0','')[:80]}")
                seen.add((r.get("base_url"), k))
            print("\n==判决==")
            for bu, k in seen:
                if k.strip() == EK:
                    print(f"  ✓ base_url={bu} key=env同款 -> 钥匙对,Groq拒绝:查IP风控/账号/模型权限")
                elif k:
                    print(f"  ✗ base_url={bu} key={mask(k)[:10]} -> 异钥匙!此指纹即凶手出生地")
                else:
                    print(f"  ✗ base_url={bu} 无api_key参数 -> 走了默认链,要查openai默认env读取路径")
    else:
        print("  (没有tap文件,先 arm)")
    print("READ_DONE")
