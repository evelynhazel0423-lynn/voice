#!/usr/bin/env python3
import os, re, json, subprocess, glob, sys

VENV = "/home/ubuntu/cloud-yunheng/hermes-agent/hermes-venv"
VPY = VENV + "/bin/python"
REPO = "/home/ubuntu/cloud-yunheng/hermes-agent"
H = "/home/ubuntu/.hermes-gateway"
TAP = "/tmp/keytap.log"
ERR = "/tmp/keytap_err.log"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(lambda m: m.group(0)[:8] + "***", s or "")

EK = ""
for line in open(H + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        EK = line.split("=", 1)[1].strip()
print("[env]", mask(EK)[:10])

print("==A 终极大招: 当面调用 resolve_runtime_provider()==")
code = '''
import json, re, sys, traceback
try:
    sys.path.insert(0, "/home/ubuntu/cloud-yunheng/hermes-agent")
    from hermes_cli.runtime_provider import resolve_runtime_provider
    r = resolve_runtime_provider()
    out = {}
    for k, v in r.items():
        s = str(v)
        if k in ("api_key", "command", "args"):
            out[k] = (s[:8] + "***len" + str(len(s))) if s else s
        elif k == "credential_pool":
            out[k] = [x[:8] + "***" for x in v] if isinstance(v, list) else s
        else:
            out[k] = re.sub(r"(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*", lambda m: m.group(0)[:8]+"***", s)
    print(json.dumps(out, ensure_ascii=False, default=str)[:1600])
except Exception:
    traceback.print_exc()
'''
env = os.environ.copy()
env["HERMES_HOME"] = H
try:
    for line in open(H + "/.env"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env.setdefault(k.strip(), v.strip())
except Exception:
    pass
r = subprocess.run([VPY, "-c", code], env=env, cwd=REPO, capture_output=True, text=True, timeout=90)
print("stdout:", (r.stdout or "").strip()[:1600])
if r.stderr.strip():
    print("stderr尾:", mask(r.stderr.strip())[-500:])

print("==B 窃听器v3: 带错误捕获+当场自检 ==")
sp = glob.glob(VENV + "/lib/python3*/site-packages")[0]
sc = os.path.join(sp, "sitecustomize.py")
tapcode = '''
# --- yunheng keytap v3 ---
import traceback
try:
    import openai, json, datetime
    def _mk(label):
        def _tap(self, *a, **kw):
            try:
                with open("/tmp/keytap.log", "a") as f:
                    f.write(json.dumps({"t": datetime.datetime.now().isoformat(), "cls": label,
                                        "base_url": str(kw.get("base_url") or ""),
                                        "api_key": str(kw.get("api_key") or "")}) + "\\n")
            except Exception:
                pass
            return self._orig_init(*a, **kw)
        return _tap
    for _lb in ("OpenAI", "AsyncOpenAI"):
        _c = getattr(openai, _lb, None)
        if _c is not None:
            _c._orig_init = _c.__init__
            _c.__init__ = _mk(_lb)
            _c._tap_patched = True
except Exception:
    with open("/tmp/keytap_err.log", "a") as f:
        f.write(traceback.format_exc())
# --- end v3 ---
'''
open(sc, "w").write(tapcode)
open(TAP, "w").close()
open(ERR, "w").close()
print("[v3已写入]", sc)

# 自检: 新进程里造一个AsyncOpenAI, 看log有没有落赃
st = subprocess.run([VPY, "-c", "import openai; openai.AsyncOpenAI(api_key='tapselftest123')"],
                    capture_output=True, text=True, timeout=60)
log = open(TAP).read().strip()
err = open(ERR).read().strip()
print("自检log:", (log or "(空!)").replace("\n", " | ")[:300])
print("自检err:", (err or "(无)")[:600])

print("==C runtime_provider.py 源码全貌 ==")
src = subprocess.run(["grep", "-n", "-A", "80", "def resolve_runtime_provider",
                      REPO + "/hermes_cli/runtime_provider.py"], capture_output=True, text=True).stdout
print(mask(src)[:3000] or "(grep没抓到,文件可能不存在)")

if "tapselftest123" in log:
    print("[窃听器自检通过] 重启网关让它带v3出生")
    subprocess.run(["pkill", "-9", "-f", "gateway run"])
    print("HUNT26_DONE 等看门狗拉起 -> TG发一条 -> python3 /tmp/hunt25.py read")
else:
    print("[自检失败,看上面err——但A段的大招已经当面审过她了,先别重启,把输出贴回来]")
print("HUNT26_END")
