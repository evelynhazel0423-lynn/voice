#!/usr/bin/env python3
# 用法: python3 hunt25.py arm   -> 双类窃听器(OpenAI+AsyncOpenAI)+重启网关
#       python3 hunt25.py read  -> 读赃出判决
import sys, os, re, subprocess, json, glob

VENV = "/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv"
H = "/home/ubuntu/.hermes-gateway"
TAP = "/tmp/keytap.log"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(r'\1****', s or "")

EK = ""
for line in open(H + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        EK = line.split("=", 1)[1].strip()

mode = sys.argv[1] if len(sys.argv) > 1 else "arm"

if mode == "arm":
    sp = glob.glob(VENV + "/lib/python3*/site-packages")[0]
    sc = os.path.join(sp, "sitecustomize.py")
    code = '''
# --- yunheng keytap v2 (OpenAI + AsyncOpenAI) ---
try:
    import openai, json, datetime, os
    def _mk_tap(label):
        def _tap(self, *a, **kw):
            try:
                with open("/tmp/keytap.log", "a") as f:
                    f.write(json.dumps({
                        "t": datetime.datetime.now().isoformat(),
                        "cls": label,
                        "base_url": str(kw.get("base_url") or getattr(self, "base_url", "") or ""),
                        "api_key": str(kw.get("api_key") or ""),
                        "kw_names": sorted(kw.keys()),
                    }) + "\\n")
            except Exception:
                pass
            return self._orig_init(*a, **kw)
        return _tap
    for _label in ("OpenAI", "AsyncOpenAI"):
        _cls = getattr(openai, _label, None)
        if _cls is not None and not getattr(_cls, "_tap_patched", False):
            _cls._orig_init = _cls.__init__
            _cls.__init__ = _mk_tap(_label)
            _cls._tap_patched = True
except Exception:
    pass
# --- end keytap v2 ---
'''
    open(sc, "w").write(code)
    print("[窃听器v2已植入] 钩了 OpenAI + AsyncOpenAI 双类:", sc)
    open(TAP, "w").close()

    # 进程环境快照
    for p in subprocess.run(["pgrep", "-f", "gateway run"], capture_output=True, text=True).stdout.split():
        try:
            env = open(f"/proc/{p}/environ", "rb").read().decode("utf-8", "ignore")
            for kv in env.split("\0"):
                if kv.startswith("OPENAI_API_KEY="):
                    v = kv.split("=", 1)[1]
                    print(f"  pid{p}: {mask(v)[:10]} [{'OK' if v.strip()==EK else '***异***'}]")
        except Exception:
            pass
    subprocess.run(["pkill", "-9", "-f", "gateway run"])
    print("[网关已杀] 看门狗拉起(带窃听器v2出生)")
    print("ARM_DONE 等2分钟 -> TG发一条 -> python3 /tmp/hunt25.py read")

elif mode == "read":
    print("== keytap.log ==")
    if os.path.exists(TAP):
        txt = open(TAP).read().strip()
        if not txt:
            print("  (还是空——看看网关进程活着没+sitecustomize加载没)")
            for p in subprocess.run(["pgrep", "-f", "gateway run"], capture_output=True, text=True).stdout.split():
                print("  网关pid:", p)
            # 验证窃听器能不能被python加载
            r = subprocess.run([VENV + "/bin/python", "-c", "import sitecustomize, openai; print('openai.__init__ patched:', hasattr(openai.AsyncOpenAI, '_tap_patched'))"], capture_output=True, text=True)
            print("  窃听器加载验证:", r.stdout.strip() or r.stderr.strip()[-200:])
        else:
            seen = set()
            for line in txt.splitlines():
                try: r = json.loads(line)
                except Exception: continue
                k = r.get("api_key", "")
                tag = "OK=env同款" if k.strip() == EK else ("***异钥匙***" if k else "(无api_key参数!)")
                print(f"  {r['t']} [{r.get('cls')}] base_url={r.get('base_url')}")
                print(f"      key={mask(k)[:12]} len={len(k)} [{tag}] kwargs={r.get('kw_names')}")
                seen.add((r.get("cls"), r.get("base_url"), k))
            print("\n==判决==")
            for cls, bu, k in seen:
                if k.strip() == EK:
                    print(f"  ✓ [{cls}] {bu} key=env同款 -> 钥匙对,Groq拒绝:查风控/IP/账号")
                elif k:
                    print(f"  ✗ [{cls}] {bu} key={mask(k)[:12]} -> 异钥匙!这把就是401元凶,指纹={mask(k)[:12]}")
                else:
                    print(f"  ✗ [{cls}] {bu} 没传api_key -> 走openai默认env链,要查进程内env被谁覆盖")
    else:
        print("  (没tap文件)")
    print("READ_DONE")
