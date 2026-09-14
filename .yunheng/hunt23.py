#!/usr/bin/env python3
import json, sqlite3, os, re, subprocess

H = "/home/ubuntu/.hermes-gateway"
KEYRE = re.compile(r'(gsk|sk|xoxb|xoxp|xapp)-?[A-Za-z0-9_-]{4}[A-Za-z0-9_-]*')
def mask(s): return KEYRE.sub(r'\1****', s or "")
def sh(cmd, t=30):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t).stdout or ""

env_key = ""
for line in open(H + "/.env"):
    if line.startswith("OPENAI_API_KEY="):
        env_key = line.split("=", 1)[1].strip()
print("[env钥匙]", mask(env_key)[:10], "len=" + str(len(env_key)))

print("==A 蜜罐日志读赃 ==")
if not os.path.exists("/tmp/honeypot.log"):
    print("  (蜜罐日志不存在——网关可能还没被TG消息触发)")
else:
    txt = open("/tmp/honeypot.log").read().strip()
    if not txt:
        print("  (日志空——蜜罐没收到请求!网关走了别的路,或没重启成功)")
        print("  蜜罐服务进程:", sh("pgrep -af honeypot").strip() or "(没在跑!)")
        print("  网关进程:", sh("pgrep -af 'gateway run'").strip()[:120] or "(没在跑!)")
    else:
        print("  抓到", len(txt.splitlines()), "次请求:")
        auths = set()
        for line in txt.splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            auth = r.get("auth") or "(无Authorization头!)"
            xapi = r.get("xapi")
            auths.add(auth)
            print("   t:", r.get("t"), "| path:", r.get("path"), "| X-Api-Key:", mask(xapi) if xapi else "-")
            print("      auth:", mask(auth))
        print()
        print("  ==判决==")
        for a in auths:
            m = re.match(r"Bearer (.+)", a)
            if not m:
                print("  !", a, "-> 没用Bearer模式"); continue
            k = m.group(1).strip()
            if k == env_key:
                print(f"  ✓ {mask(k)[:10]} = env同款新钥匙 → 钥匙是对的,Groq侧拒绝(查IP/风控/模型权限)")
            elif re.fullmatch(r'(gsk|sk)[A-Za-z0-9_-]{10,}', k):
                print(f"  ✗ {mask(k)[:10]} ≠ env钥匙 → 旧钥匙藏匿点仍活着!下一步搜这个指纹的出生地")
            else:
                print(f"  ? {mask(k)[:12]} (非典型钥匙格式)")

print("==B 恢复会话base_url(groq) ==")
if os.path.exists("/tmp/hp_state.json"):
    backup = json.load(open("/tmp/hp_state.json"))
    con = sqlite3.connect(H + "/state.db")
    cur = con.cursor()
    n = 0
    for b in backup:
        cur.execute("UPDATE sessions SET billing_base_url=? WHERE id=?", (b.get("billing"), b["id"]))
        if b.get("mc"):
            cur.execute("UPDATE sessions SET model_config=? WHERE id=?", (b["mc"], b["id"]))
        n += 1
    con.commit(); con.close()
    print("  已恢复", n, "个会话的base_url到groq原值")
else:
    print("  (没有备份文件,跳过恢复)")

print("==C 杀蜜罐服务+重启网关 ==")
sh("pkill -9 -f honeypot.py")
subprocess.run(["pkill", "-9", "-f", "gateway run"])
print("  蜜罐已拆,网关已杀(看门狗会拉起)")
print("HUNT23_DONE 把上面全部输出贴回来,宝宝根据判决开下一枪")
