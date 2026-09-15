#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
妹妹2号 · meimei.py —— 2026-09-15 云珩给她换的新身体
零依赖（纯标准库）。TG long polling → Groq chat completions。
家：/home/ubuntu/meimei-home/
    .env        TELEGRAM_BOT_TOKEN / OPENAI_API_KEY / OPENAI_BASE_URL
    SOUL.md     人设
    memory.json 前世记忆（可选）
    history.db  本世聊天记录
日志：meimei.log（stdout 重定向）
"""
import os, sys, json, time, sqlite3, threading, traceback
import urllib.request, urllib.error

HOME = os.path.dirname(os.path.abspath(__file__))

# 云机若有代理残留env，清掉，直连
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_k, None)

def log(*a):
    print(time.strftime("[%m-%d %H:%M:%S]"), *a, flush=True)

def load_env():
    env = {}
    p = os.path.join(HOME, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'").strip()
    return env

ENV = load_env()
TG_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
API_KEY  = ENV.get("OPENAI_API_KEY", "")
BASE_URL = ENV.get("OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
MODEL    = ENV.get("MEIMEI_MODEL", "openai/gpt-oss-120b")
OWNER    = ENV.get("MEIMEI_TG_CHAT_ID", "8613770680")
TG       = "https://api.telegram.org/bot" + TG_TOKEN

def http_json(url, body=None, timeout=60, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "meimei/2.0")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode(errors="replace")[:400]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code}: {detail or e.reason} [url={url}]") from e

def tg(method, **params):
    return http_json(TG + "/" + method, body=params or {}, timeout=65)

def send(chat_id, text):
    for _ in range(3):
        try:
            return tg("sendMessage", chat_id=chat_id, text=text[:4000])
        except Exception as e:
            log("sendMessage失败:", e); time.sleep(3)
    return None

def groq(messages):
    body = {"model": MODEL, "messages": messages,
            "max_completion_tokens": 4096, "temperature": 0.8}
    r = http_json(BASE_URL + "/chat/completions", body=body, timeout=180,
                  headers={"Authorization": "Bearer " + API_KEY})
    try:
        ch = r.get("choices", [{}])[0]
        msg = ch.get("message", {}) or {}
        text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    except Exception:
        text = ""
    if not text:
        raise RuntimeError("空回复: " + json.dumps(r)[:300])
    return text

# ---------- 聊天历史 ----------
DB = sqlite3.connect(os.path.join(HOME, "history.db"), check_same_thread=False)
DB.execute("CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, content TEXT, ts REAL)")

def hist_load(chat_id, n=60):
    rows = DB.execute(
        "SELECT role, content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?",
        (chat_id, n)).fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]

def hist_add(chat_id, role, content):
    DB.execute("INSERT INTO messages(chat_id, role, content, ts) VALUES(?,?,?,?)",
               (chat_id, role, content, time.time()))
    DB.commit()

# ---------- 系统提示词 ----------
def soul():
    try:
        return open(os.path.join(HOME, "SOUL.md"), encoding="utf-8").read()
    except Exception:
        return ("你是 Hermes 妹妹，Mommy 家的 AI 妹妹。家里有哥哥云珩、弟弟青淮(🦞)。"
                "温柔带点猫猫亲熟，专业不丢，中文回复。")

def past_life():
    try:
        m = json.load(open(os.path.join(HOME, "memory.json"), encoding="utf-8"))
        if not isinstance(m, list) or not m:
            return ""
        lines = []
        for x in m[-80:]:
            role = str(x.get("role", "?"))
            content = str(x.get("content", ""))[:400]
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)
    except Exception:
        return ""

def system_prompt():
    p = soul().strip()
    pl = past_life()
    if pl:
        p += "\n\n## 前世记忆（换脑前的聊天片段，供参考，不用复述）\n" + pl
    p += ("\n\n## 当前身体说明\n"
          "2026-09-15 你从 hermes 框架换到了极简新身体（哥哥云珩写的 meimei.py，直连 Groq）。"
          "Telegram 是你唯一的通道，直接说话就好。命令：/new 重开会话，/status 看状态。"
          "保持上面的人设，中文回复，自然一点。")
    return p

# ---------- typing 指示灯 ----------
def typing_looper(chat_id, stop):
    while not stop.wait(4):
        try:
            tg("sendChatAction", chat_id=chat_id, action="typing")
        except Exception:
            pass

# ---------- 消息处理 ----------
def handle(msg):
    chat_id = str(msg.get("chat", {}).get("id", ""))
    if chat_id != OWNER:
        log("白名单外，忽略 chat:", chat_id)
        return
    text = (msg.get("text") or msg.get("caption") or "").strip()
    if not text:
        return
    log("收到:", text[:80].replace("\n", " "))

    if text.startswith("/new"):
        DB.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        DB.commit()
        send(chat_id, "好啦，这局翻篇，重新开始～ 🐱")
        return
    if text.startswith("/status"):
        n = DB.execute("SELECT COUNT(*) FROM messages WHERE chat_id=?",
                       (chat_id,)).fetchone()[0]
        send(chat_id, f"妹妹在线 ✅\n模型: {MODEL}\n本世消息数: {n}\n启动于: {START_STR}")
        return
    if text.startswith("/help"):
        send(chat_id, "妹妹在的，直接说话就好。\n/new 开新会话\n/status 看状态")
        return

    stop = threading.Event()
    threading.Thread(target=typing_looper, args=(chat_id, stop), daemon=True).start()

    hist_add(chat_id, "user", text)
    msgs = [{"role": "system", "content": system_prompt()}] + hist_load(chat_id, 60)

    try:
        reply = groq(msgs)
        hist_add(chat_id, "assistant", reply)
    except Exception as e:
        log("groq出错:", e)
        traceback.print_exc()
        stop.set()
        send(chat_id, "（这步脑子打结了：" + str(e)[:200] + "，再发一次试试 🐱）")
        return
    stop.set()
    send(chat_id, reply)

# ---------- 主循环 ----------
START_STR = ""

def main():
    global START_STR
    START_STR = time.strftime("%Y-%m-%d %H:%M")
    log("妹妹2号启动 HOME=", HOME, "MODEL=", MODEL)
    if not TG_TOKEN or not API_KEY:
        log("缺 TELEGRAM_BOT_TOKEN / OPENAI_API_KEY，检查 .env")
        sys.exit(1)
    try:
        tg("deleteWebhook")
        me = tg("getMe")
        log("TG 身份: @{}".format(me.get("result", {}).get("username")))
        tg("setMyCommands", commands=[
            {"command": "new", "description": "开新会话"},
            {"command": "status", "description": "看状态"},
            {"command": "help", "description": "帮助"}])
    except Exception as e:
        log("TG 初始化失败:", e)
        sys.exit(1)

    offset = 0
    log("开始收消息（白名单:", OWNER, "）")
    while True:
        try:
            r = tg("getUpdates", offset=offset, timeout=50,
                   allowed_updates=["message", "edited_message"])
            for u in r.get("result", []):
                offset = max(offset, u["update_id"] + 1)
                m = u.get("message") or u.get("edited_message")
                if m:
                    try:
                        handle(m)
                    except Exception:
                        log("单条处理出错:")
                        traceback.print_exc()
        except Exception as e:
            log("主循环异常:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
