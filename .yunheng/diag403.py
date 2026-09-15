#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diag403.py —— 云机侧 Groq 403 诊断 · 云珩 2026-09-15
黑窗口：curl -sL https://raw.githubusercontent.com/evelynhazel0423-lynn/voice/main/.yunheng/diag403.py -o /tmp/d.py && python3 /tmp/d.py
全程打码：key 只显示前8位。"""
import json, os, urllib.request, urllib.error, ssl

print("=" * 8, "Groq 403 诊断", "=" * 8)

# 0. 出口IP
ip = ""
try:
    ip = urllib.request.urlopen("https://checkip.amazonaws.com", timeout=15).read().decode().strip()
except Exception as e:
    ip = f"(拿不到:{e})"
print("[0] 云机出口IP:", ip)

# 1. 读 key（打码）
EK = ""
home = "/home/ubuntu/meimei-home/.env"
if os.path.exists(home):
    for line in open(home, errors="ignore"):
        if line.startswith("OPENAI_API_KEY="):
            EK = line.split("=", 1)[1].strip().strip('"').strip("'").strip()
print("[1] meimei-home/.env 的key:", (EK[:8] + "…" + f"(len={len(EK)})") if EK else "(没读到!)")

# 2. 同一进程三种姿势打 /models
def hit(label, req):
    try:
        r = urllib.request.urlopen(req, timeout=30)
        print(f"  {label} -> {r.status} {r.read().decode(errors='replace')[:150]}")
        return True
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode(errors="replace")[:300]
        except Exception:
            pass
        print(f"  {label} -> HTTP {e.code} {body or e.reason}")
        print(f"    响应头: {dict(list(e.headers.items())[:6])}")
    except Exception as e:
        print(f"  {label} -> 异常 {repr(e)[:150]}")
    return False

import socket, ssl as _ssl
print("[2] DNS/握手:")
try:
    print("   api.groq.com ->", socket.gethostbyname("api.groq.com"))
except Exception as e:
    print("   DNS挂了:", e)

print("[3] GET /models 三姿势:")
hit("A裸", urllib.request.Request("https://api.groq.com/openai/v1/models"))
r = urllib.request.Request("https://api.groq.com/openai/v1/models")
r.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
hit("B浏览器UA", r)
if EK:
    r = urllib.request.Request("https://api.groq.com/openai/v1/models")
    r.add_header("Authorization", "Bearer " + EK)
    r.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
    if hit("C真key+浏览器UA", r):
        print("   ^^^ 这条 200 = key好、IP好，是UA问题 → 换UA就能修")

print("[4] POST /chat/completions 真弹（真key+浏览器UA）:")
if EK:
    body = json.dumps({"model": "openai/gpt-oss-120b", "max_completion_tokens": 16,
                       "messages": [{"role": "user", "content": "ping"}]}).encode()
    r = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=body, method="POST")
    r.add_header("Content-Type", "application/json")
    r.add_header("Authorization", "Bearer " + EK)
    r.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
    try:
        resp = urllib.request.urlopen(r, timeout=60)
        d = json.loads(resp.read().decode())
        txt = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
        print("   POST 200！回复:", txt[:100])
        print("DIAG_GOOD: key+IP+UA全通，问题不在云机侧")
    except urllib.error.HTTPError as e:
        b = e.read().decode(errors="replace")[:300]
        print(f"   POST HTTP {e.code}: {b}")
        if e.code == 401:
            print("   ^^^ 401 invalid key = 这把钥匙真失效了 → 需要妈妈换新key")
        elif e.code == 403:
            print("   ^^^ 403 = IP被Groq拒(或钥匙无权限)，需要换出口或换key")
        elif e.code == 429:
            print("   ^^^ 429 限流 = key好，等等就行")
    except Exception as e:
        print("   异常:", repr(e)[:150])

print("[5] 对照: curl 姿势（绕python栈）:")
os.system("curl -s -o /dev/null -w 'curl /models: %{http_code}\\n' -m 20 https://api.groq.com/openai/v1/models")
if EK:
    os.system(f"curl -s -m 30 -H 'Authorization: Bearer {EK}' https://api.groq.com/openai/v1/models | head -c 200; echo")

print("DIAG_DONE 把上面全部贴回来给云珩")
