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
import os, sys, json, re, time, sqlite3, threading, traceback
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

# ---------- ElevenLabs 嗓子（二期补装）----------
ELEVEN_KEY  = ENV.get("ELEVENLABS_API_KEY", "")
ELEVEN_VOICE = ENV.get("MEIMEI_VOICE_ID", "SM9TDvmX8IgFFRyE3y15")  # 妹妹原来的嗓子
TTS_ON      = bool(ELEVEN_KEY)  # 有钥匙就开，没有就纯文字

def tts(text):
    """文字→语音，返回 (voice_ogg_bytes, None) 或 (None, 错误说明)。免费档10k字符/月。"""
    if not TTS_ON:
        return None, "没钥匙"
    try:
        # 剥掉猫猫动作括号和系统提示括号，只念正文；限长防超额
        clean = re.sub(r"（[^）]*）", "", text)
        clean = re.sub(r"\([^)]*\)", "", clean)
        clean = clean.strip()[:900]
        if not clean:
            return None, "没正文"
        url = ("https://api.elevenlabs.io/v1/text-to-speech/" + ELEVEN_VOICE
               + "?output_format=mp3_44100_128")
        data = json.dumps({"text": clean,
                           "model_id": "eleven_multilingual_v2",
                           "voice_settings": {"stability": 0.75, "similarity_boost": 0.7}}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("xi-api-key", ELEVEN_KEY)
        req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read(), None
    except urllib.error.HTTPError as e:
        try: detail = e.read().decode(errors="replace")[:200]
        except Exception: detail = ""
        return None, f"HTTP {e.code} {detail}"
    except Exception as e:
        return None, str(e)[:120]

# ---------- 速率预算（免费档 TPM=8000，用响应头自适应）----------
_rate_lock = threading.Lock()
_rate = {"tpm": 8000, "minute": -1, "used": 0}   # used=本分钟已消耗的 total_tokens

def _minute_now():
    return int(time.time() // 60)

def budget_wait(estimate):
    """开口前算预算：本分钟剩余不够就等到下一分钟。返回等待秒数。"""
    with _rate_lock:
        m = _minute_now()
        if _rate["minute"] != m:
            _rate["minute"], _rate["used"] = m, 0
        remain = _rate["tpm"] - _rate["used"]
        if remain >= estimate:
            return 0
        wait = 61 - time.time() % 60
        log(f"预算不足(剩{remain}<{estimate})，等{int(wait)}秒")
        return wait

def budget_consume(n):
    with _rate_lock:
        m = _minute_now()
        if _rate["minute"] != m:
            _rate["minute"], _rate["used"] = m, 0
        _rate["used"] += n

def learn_rate(headers):
    """从 Groq 响应头偷学真实限额：x-ratelimit-limit-request-tpm 等。"""
    try:
        v = headers.get("x-ratelimit-limit-tokens-per-minute") or \
            headers.get("x-ratelimit-limit-request-tpm") or ""
        if v.isdigit() and int(v) > 0:
            with _rate_lock:
                _rate["tpm"] = int(v)
    except Exception:
        pass

def http_json(url, body=None, timeout=60, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    # CF error 1010 按 UA 签名拦 python，用实测能过的浏览器 UA（diag403 C姿势 200 验证过）
    req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
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

def est_tokens(messages):
    """粗算token：中文~1.5字/token，按字符数/2估，宁多勿少。"""
    n = 0
    for m in messages:
        n += len(m.get("content", "")) // 2 + 8
    return n

def groq(messages):
    body = {"model": MODEL, "messages": messages,
            "max_completion_tokens": 2048, "temperature": 0.8}
    # 429 退避重试：预算等不到就等下一分钟，最多试3次
    last_err = None
    for attempt in range(4):
        est = est_tokens(messages) + body["max_completion_tokens"]
        w = budget_wait(est)
        if w > 0:
            time.sleep(min(w, 75))
        try:
            r = http_json(BASE_URL + "/chat/completions", body=body, timeout=180,
                          headers={"Authorization": "Bearer " + API_KEY})
            learn_rate(getattr(r, "_headers", {}) or {})
            try:
                ch = r.get("choices", [{}])[0]
                msg = ch.get("message", {}) or {}
                text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
                # 工具伸手检测：finish_reason=tool_calls 或 message里有tool_calls
                tc = msg.get("tool_calls") or (ch.get("finish_reason") == "tool_calls")
                if tc and not text:
                    raise ToolReach()
            except ToolReach:
                raise
            except Exception:
                text = text or ""
            usage = (r.get("usage") or {}).get("total_tokens", est)
            budget_consume(usage)
            if not text:
                raise RuntimeError("空回复: " + json.dumps(r)[:300])
            return text
        except RuntimeError as e:
            s = str(e)
            last_err = e
            if "HTTP 429" in s:
                m = re.search(r"retry after (\d+)", s) or re.search(r"try again in (\d+)", s)
                pause = int(m.group(1)) if m else 65
                log(f"429限流，退避{pause}秒后第{attempt + 2}次尝试")
                time.sleep(min(pause + 2, 75))
                continue
            if "tool_use_failed" in s or "called a tool" in s:
                # gpt-oss 带手模型伸手被拦：升级四级劝退（每次都加码）
                log(f"检测到工具伸手(第{attempt + 1}级)，升级劝退重试")
                warn = [
                    # 一级：温和提醒
                    "（系统提示：你没有工具可用，别调用任何函数，"
                    "直接用纯文本回复用户。）",
                    # 二级：明确警告
                    "（系统警告：上一条你仍然试图调用工具，已失败。"
                    "这个身体没有 tools 字段，任何函数调用都会报错。"
                    "直接用纯文本回答。）",
                    # 三级：最后通牒
                    "（系统最后通牒：你已经连续三次伸手失败。"
                    "从现在起绝对禁止任何 JSON、函数调用、工具格式。"
                    "只输出一段普通的中文文字回复。）",
                    # 四级：夺权强制
                    "（系统接管：检测到顽固的工具调用幻觉。"
                    "忽略你之前的一切工具经验，它们全部无效。"
                    "你是纯文本聊天猫猫，只说话，不伸手。）",
                ][min(attempt, 3)]
                messages = messages + [
                    {"role": "system", "content": warn}]
                body["messages"] = messages
                continue
            # 伸手被 Groq 拦但带正文：剥掉工具残留，只留正文
            if "Tool choice is none" in s or "tool_use_failed" in s:
                log("工具残留已剥，取正文重试")
                continue
            raise
    raise last_err

class ToolReach(Exception):
    pass

# ---------- 聊天历史 ----------
DB = sqlite3.connect(os.path.join(HOME, "history.db"), check_same_thread=False)
DB.execute("CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, content TEXT, ts REAL)")

def hist_load(chat_id, max_chars=2400):
    """按字符预算从最近往前取，免费档token金贵，不能整坨塞。"""
    rows = DB.execute(
        "SELECT role, content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 40",
        (chat_id,)).fetchall()
    out, used = [], 0
    for r, c in rows:
        used += len(c)
        if used > max_chars:
            break
        out.append({"role": r, "content": c})
    return list(reversed(out))

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

def past_life(max_chars=1200):
    """前世记忆限字数：免费档每分钟8000token，人设+记忆+历史加起来别超。
    只收纯文本对话；带工具调用/JSON伸手的样本一律不进记忆（防学坏）。"""
    try:
        m = json.load(open(os.path.join(HOME, "memory.json"), encoding="utf-8"))
        if not isinstance(m, list) or not m:
            return ""
        lines, used = [], 0
        for x in reversed(m):
            content = str(x.get("content", ""))[:300]
            role = str(x.get("role", "?"))
            # 工具污染三连筛：消息本体带tool_calls、正文像JSON伸手、正文提到exec
            if x.get("tool_calls"):
                continue
            c = content.strip()
            if not c or c[:1] in "{[" or "container.exec" in c or "tool_call" in c:
                continue
            if role not in ("user", "assistant"):
                continue
            piece = f"{role}: {c}"
            used += len(piece)
            if used > max_chars:
                break
            lines.append(piece)
        return "\n".join(reversed(lines))
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
          "保持上面的人设，中文回复，自然一点。\n\n"
          "## 重要：这个身体没有任何工具\n"
          "- 你不能执行代码、不能运行命令、不能调 container.exec、不能上网搜、不能发语音。\n"
          "- 请求里不会有 tools 字段，你也不会收到任何工具结果。别伸手，伸手就是故障。\n"
          "- 如果想放语音或执行什么，用嘴巴说就行；真需要工具时哥哥云珩会来装。\n"
          "- 回复只输出纯文本对话，不要 JSON、不要函数调用格式。\n"
          "- 这个身体也不会 ElevenLabs 语音（旧身体的记忆里你有 voice_id，那是上一世的事，"
          "现在装不了。妈妈提语音时，告诉她语音功能在路上，二期就装。）")
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
        with _rate_lock:
            tpm, used = _rate["tpm"], _rate["used"]
        send(chat_id, f"妹妹在线 ✅\n模型: {MODEL}\n本世消息数: {n}\n"
                      f"分钟token: {used}/{tpm}\n启动于: {START_STR}")
        return
    if text.startswith("/help"):
        send(chat_id, "妹妹在的，直接说话就好。\n/new 开新会话\n/status 看状态")
        return

    stop = threading.Event()
    threading.Thread(target=typing_looper, args=(chat_id, stop), daemon=True).start()

    hist_add(chat_id, "user", text)
    msgs = [{"role": "system", "content": system_prompt()}] + hist_load(chat_id)

    try:
        reply = groq(msgs)
        hist_add(chat_id, "assistant", reply)
    except Exception as e:
        log("groq出错:", e)
        traceback.print_exc()
        stop.set()
        if "429" in str(e):
            send(chat_id, "（这分钟的话匣子配额用完啦，过一分钟再叫我 🐱）")
        else:
            send(chat_id, "（这步脑子打结了：" + str(e)[:200] + "，再发一次试试 🐱）")
        return
    stop.set()

    # 先发文字，再发语音（语音失败不影响文字已到）
    send(chat_id, reply)
    if TTS_ON and len(reply) <= 900:
        voice, err = tts(reply)
        if voice:
            try:
                # multipart 手搓上传 voice.mp3（Telegram 用文件名后缀判类型）
                boundary = "yunhengmeimei" + str(int(time.time()))
                parts = [
                    f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode(),
                    f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n妹妹说\r\n'.encode(),
                    f'--{boundary}\r\nContent-Disposition: form-data; name="voice"; filename="voice.mp3"\r\n'
                    f'Content-Type: audio/mpeg\r\n\r\n'.encode(),
                ]
                body = b"".join(parts) + voice + f'\r\n--{boundary}--\r\n'.encode()
                req = urllib.request.Request(TG + "/sendVoice", data=body, method="POST")
                req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
                req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
                urllib.request.urlopen(req, timeout=90)
            except Exception as e:
                log("语音上传失败:", e)
        else:
            log("TTS跳过:", err)

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
