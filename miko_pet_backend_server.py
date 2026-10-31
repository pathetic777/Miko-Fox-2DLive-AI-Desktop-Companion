# -*- coding: utf-8 -*-
"""
Decoupled Dual-Channel Backend Server for Shrine Maiden & Little White Fox 2D Live Desktop Companion (English Edition)
Port: http://127.0.0.1:18766
Features:
- Channel 1 API (Dialogue): Pure Shrine Maiden roleplay reply without any code tags polluting the text or TTS.
- Channel 2 API (MVU Expression Controller): Dedicated second API request with a strict MVU System Prompt
  that judges the context and outputs `<<mvu:set_expr("expr1..expr9")>>`, parsed via regex to automatically
  drive the 9 Diffusion-generated Shrine Maiden expressions!
- Built-in Voice Toggle (`builtin_voice_enabled`): One-click switch to mute/enable the built-in VOICEVOX:Amahare Hau bonus voice.
- Multi-Channel Custom TTS Binding: Cloud OpenAI-compatible TTS (`/v1/audio/speech`), Local GPT-SoVITS (`127.0.0.1:9880`),
  Local VOICEVOX Engine (`127.0.0.1:50021`), or Windows SAPI fallback.
- Little White Fox Tail App Binding (`bound_app_path`): Native file picker (`/api/browse_app`) & launcher (`/api/launch_bound_app`).
"""
import os
import sys
import re
import json
import time
import random
import threading
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT = 18766
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HTML_FILE = os.path.join(BASE_DIR, "Web_Control_Center.html")
CONFIG_FILE = os.path.join(BASE_DIR, "pet_config.json")
STARTUP_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup",
)
STARTUP_VBS = os.path.join(STARTUP_DIR, "MikoFoxDesktopPet_AutoStart.vbs")
PYTHONW_EXE = r"D:\bilibili_animation_study\see-through\venv\Scripts\pythonw.exe"
if not os.path.exists(PYTHONW_EXE):
    PYTHONW_EXE = sys.executable.replace("python.exe", "pythonw.exe")

VALID_EXPRESSIONS = [
    "expr1",  # ① Gentle Smile
    "expr2",  # ② Beaming Smile
    "expr3",  # ③ Starry Pride
    "expr4",  # ④ Loving Heart Eyes
    "expr5",  # ⑤ Shy Blush
    "expr6",  # ⑥ Flinching Bashful
    "expr7",  # ⑦ Pouty Angry
    "expr8",  # ⑧ Teary Grievance
    "expr9",  # ⑨ Darkened Wrath / Divine Punishment
]

EXPR_TITLES = {
    "expr1": "① Gentle Smile",
    "expr2": "② Beaming Smile",
    "expr3": "③ Starry Pride",
    "expr4": "④ Loving Heart Eyes",
    "expr5": "⑤ Shy Blush",
    "expr6": "⑥ Flinching Bashful",
    "expr7": "⑦ Pouty Angry",
    "expr8": "⑧ Teary Grievance",
    "expr9": "⑨ Darkened Wrath",
}

DEFAULT_MVU_SYSTEM_PROMPT = """Based on the [User Message] and [Shrine Maiden's Reply], choose ONE of the 9 expressions below and output ONLY the single command line:
<<mvu:set_expr("expr_id")>>

Available Expression IDs:
- expr1 : ① Gentle Smile (Default idle, calm everyday chat)
- expr2 : ② Beaming Smile (Happy, joyful, or when head-patted)
- expr3 : ③ Starry Pride (Finished sweeping, proud, confident, energetic)
- expr4 : ④ Loving Heart Eyes (Affectionate, loving, or petting the little white fox)
- expr5 : ⑤ Shy Blush (Complimented, bashful, blushing cheeks)
- expr6 : ⑥ Flinching Bashful (Teased, flustered, shyly refusing)
- expr7 : ⑦ Pouty Angry (Jealous, pouting, sulking, mildly annoyed)
- expr8 : ⑧ Teary Grievance (Sad, hurt, bullied, on the verge of tears)
- expr9 : ⑨ Darkened Wrath (Maximum anger, divine punishment, slap penalty)

IMPORTANT: Output ONLY the single command line such as <<mvu:set_expr("expr5")>> with no explanation."""

DEFAULT_CONFIG = {
    "name": "Hidzuki (Shrine Maiden)",
    "greeting": "Welcome back! Little White Fox and I are always right here in the bottom-right corner of your desktop♪",
    "base_url": "",
    "api_key": "",
    "model": "",
    "temperature": 0.78,
    "builtin_voice_enabled": True,
    "tts_enabled": True,
    "tts_channel": "cloud",
    "cloud_tts_url": "",
    "cloud_tts_key": "",
    "cloud_tts_model": "",
    "cloud_tts_voice": "",
    "local_tts_url": "http://127.0.0.1:9880",
    "local_ref_wav": "",
    "local_ref_text": "",
    "local_ref_lang": "en",
    "voicevox_url": "http://127.0.0.1:50021",
    "voicevox_speaker": 10,
    "bound_app_path": "",
    "bound_app_name": "",
    "system_prompt": (
        "You are 'Hidzuki', a shrine maiden standing quietly in the bottom-right corner of the user's Windows desktop. "
        "You hold a bamboo broom in both hands, and a clever little white fox rests by your feet. "
        "You are gentle, graceful, and supportive, with a slightly tsundere and cute side. "
        "You sweep unwanted files into the Recycle Bin with your bamboo broom, and your little white fox wags its tail to launch the user's favorite apps. "
        "If someone pokes your chest 5 times in a row, you blush furiously, shout 'Kyaa...! Pervert!', and deliver a slap with a 20-second shutdown divine punishment. "
        "Always reply naturally in English in 1 to 2 short, warm sentences."
    ),
    "mvu_system_prompt": DEFAULT_MVU_SYSTEM_PROMPT,
    "current_expression": "expr1",
    "last_mvu_code": '<<mvu:set_expr("expr1")>>',
    "last_reply": "",
    "last_desktop_chat_id": 0,
    "last_desktop_user_msg": "",
    "last_desktop_reply": "",
    "speak_until_ts": 0.0,
    "updated_at": 0.0,
}


_CONFIG_LOCK = threading.RLock()


def sanitize_system_prompt(prompt: str) -> str:
    p = (prompt or "").strip()
    p = re.sub(r"[（\(]\s*\d+\s*(?:文字以内|chars?|characters?)\s*[）\)]", "briefly", p, flags=re.IGNORECASE)
    return p


def load_config() -> dict:
    with _CONFIG_LOCK:
        cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    cfg.update(saved)
            except Exception:
                pass
        if isinstance(cfg.get("system_prompt"), str):
            cfg["system_prompt"] = sanitize_system_prompt(cfg["system_prompt"])
        return cfg


def save_config(new_data: dict) -> dict:
    with _CONFIG_LOCK:
        cfg = load_config()
        for k in DEFAULT_CONFIG.keys():
            if k in new_data and new_data[k] is not None:
                cfg[k] = new_data[k]
        if isinstance(cfg.get("system_prompt"), str):
            cfg["system_prompt"] = sanitize_system_prompt(cfg["system_prompt"])
        cfg["updated_at"] = time.time()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return cfg


def regex_parse_mvu_code(raw_mvu_output: str, fallback_context: str = "") -> tuple:
    """
    Uses Regex to parse the Channel 2 MVU command (`<<mvu:set_expr("expr5")>>`)
    and returns `(expr_id, canonical_mvu_code)`.
    """
    text = (raw_mvu_output or "").strip()
    m = re.search(r'set_expr\s*\(\s*["\']?([a-zA-Z0-9_]+)["\']?\s*\)', text, flags=re.IGNORECASE)
    if m:
        cand = m.group(1).lower().strip()
        if cand in VALID_EXPRESSIONS:
            return cand, f'<<mvu:set_expr("{cand}")>>'

    for expr_id in VALID_EXPRESSIONS:
        if re.search(rf"\b{expr_id}\b", text.lower()):
            return expr_id, f'<<mvu:set_expr("{expr_id}")>>'

    combined = (text + " " + fallback_context).lower()
    if any(w in combined for w in ["punish", "slap", "shutdown", "restart", "pervert", "wrath", "天罰", "エッチ"]):
        expr = "expr9"
    elif any(w in combined for w in ["cry", "tear", "sad", "mean", "bully", "uninstall", "delete me", "sob", "🥺"]):
        expr = "expr8"
    elif any(w in combined for w in ["hmph", "pout", "angry", "mad", "idiot", "stupid", "hate", "jealous", "💢"]):
        expr = "expr7"
    elif any(w in combined for w in ["don't touch", "stop", "no!", "kya", "perv", "lewd", "fluster"]):
        expr = "expr6"
    elif any(w in combined for w in ["blush", "shy", "cute", "pretty", "beautiful", "gorgeous", "///", "😳"]):
        expr = "expr5"
    elif any(w in combined for w in ["love", "adore", "marry", "fox", "tail", "hug", "kiss", "heart", "💕"]):
        expr = "expr4"
    elif any(w in combined for w in ["sweep", "broom", "clean", "trash", "recycle", "proud", "leave it to me", "✨"]):
        expr = "expr3"
    elif any(w in combined for w in ["happy", "glad", "morning", "hello", "hi ", "pat", "thank", "welcome", "smile"]):
        expr = "expr2"
    else:
        expr = "expr1"

    return expr, f'<<mvu:set_expr("{expr}")>>'


def strip_any_mvu_tags(dialogue_text: str) -> str:
    t = (dialogue_text or "").strip()
    t = re.sub(r"<<\s*mvu\s*:[^>]+>>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<mvu>[\s\S]*?</mvu>", "", t, flags=re.IGNORECASE)
    t = re.sub(r'set_expr\s*\(\s*["\']?[a-zA-Z0-9_]+["\']?\s*\)', "", t, flags=re.IGNORECASE)
    t = re.sub(r"[\(（\[【<＜][^\)）\]】>＞]{0,12}?[\d０-９]+\s*(?:文字|字|chars?|characters?|words?)[^\)）\]】>＞]*[\)）\]】>＞]", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*[\d０-９]+\s*文字\s*$", "", t)
    return t.strip()


def normalize_base_url(raw_url: str) -> str:
    u = (raw_url or "").strip().rstrip("/")
    for suffix in ["/v1/chat/completions", "/chat/completions", "/v1/models", "/models", "/api/tags", "/v1"]:
        if u.lower().endswith(suffix):
            u = u[: -len(suffix)].rstrip("/")
    return u


def build_headers(api_key: str):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MikoFoxDesktopPet/2.0",
    }
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    return headers


def call_channel2_mvu_api(base_url: str, api_key: str, model: str, user_msg: str, bot_reply: str, mvu_sys_prompt: str = "") -> tuple:
    sys_p = (mvu_sys_prompt or DEFAULT_MVU_SYSTEM_PROMPT).strip()
    user_p = f"[User Message]: {user_msg}\n[Shrine Maiden's Reply]: {bot_reply}\nOutput ONLY the single-line expression command:"

    if base_url and model and (api_key or "127.0.0.1" in base_url or "localhost" in base_url):
        headers = build_headers(api_key)
        req_body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": sys_p},
                {"role": "user", "content": user_p},
            ],
            "temperature": 0.1,
            "max_tokens": 30,
        }).encode("utf-8")

        for url in [f"{base_url}/v1/chat/completions", f"{base_url}/chat/completions"]:
            try:
                req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    data = json.loads(raw)
                    if isinstance(data.get("choices"), list) and data["choices"]:
                        raw_out = (data["choices"][0].get("message") or {}).get("content") or ""
                        return regex_parse_mvu_code(raw_out, user_msg + " " + bot_reply)
            except Exception:
                pass

    return regex_parse_mvu_code("", user_msg + " " + bot_reply)


def local_contextual_reply(user_msg: str) -> str:
    u = (user_msg or "").strip().lower()
    if any(k in u for k in ["cute", "pretty", "beautiful", "gorgeous", "lovely", "adorable"]):
        return "E-Eh?! Calling a shrine maiden cute out of nowhere... even the little white fox at my feet is giggling at me ///"
    if any(k in u for k in ["love", "like you", "marry", "waifu", "hug", "kiss"]):
        return "H-Hmph... since you say it so sincerely, Little White Fox and I will stay by your side in the corner of your screen forever 💕"
    if any(k in u for k in ["sweep", "broom", "clean", "trash", "recycle", "file"]):
        return "Leave it to me! Drag any unwanted file onto my bamboo broom and I'll sweep it straight into the Recycle Bin ✨"
    if any(k in u for k in ["fox", "tail", "launch", "app", "open"]):
        return "This little white fox is super clever! Click its fluffy tail and it'll wag happily while launching your bound app♪"
    if any(k in u for k in ["chest", "boob", "touch", "poke", "slap", "shutdown"]):
        return "Kyaa...! If you keep poking me there, I'll deliver a divine slap and a 20-second shutdown punishment! ⚡"
    if any(k in u for k in ["stupid", "idiot", "hate", "shut up", "annoying"]):
        return "Hmph! How dare you speak to a shrine maiden like that? I'll sweep you into the Recycle Bin with my bamboo broom! 💢"
    if any(k in u for k in ["delete", "uninstall", "remove", "bye", "leave"]):
        return "Uuu... Little White Fox and I wait here every day to keep your desktop clean... are you really going to leave us behind? 🥺"
    if any(k in u for k in ["hello", "hi", "hey", "morning", "evening", "thank", "pat", "good"]):
        return "Ehehe, thank you for the head pat♪ May the shrine's blessings bring you good fortune today ^_^"
    return "I'm always watching over you from the bottom-right corner♪ Drag files onto my bamboo broom to clean up, or click the fox's tail to launch your app!"


def is_autostart_enabled() -> bool:
    return os.path.exists(STARTUP_VBS)


def set_autostart(enable: bool) -> bool:
    os.makedirs(STARTUP_DIR, exist_ok=True)
    if enable:
        if getattr(sys, "frozen", False):
            target_cmd = f'"""{sys.executable}"""'
        else:
            pet_py = os.path.join(BASE_DIR, "miko_desktop_pet_app.py")
            target_cmd = f'"""{PYTHONW_EXE}"" ""{pet_py}"""'
        vbs_code = (
            'Set WshShell = CreateObject("WScript.Shell")\r\n'
            f'WshShell.CurrentDirectory = "{BASE_DIR}"\r\n'
            f'WshShell.Run {target_cmd}, 0, False\r\n'
        )
        with open(STARTUP_VBS, "w", encoding="mbcs", errors="replace") as f:
            f.write(vbs_code)
    else:
        if os.path.exists(STARTUP_VBS):
            try:
                os.remove(STARTUP_VBS)
            except Exception:
                pass
    return is_autostart_enabled()


class MikoPetBackendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def log_message(self, format, *args):
        pass

    def _send_json(self, data: dict, status: int = 200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/status") or self.path.startswith("/api/ping"):
            cfg = load_config()
            self._send_json({
                "ok": True,
                "service": "miko_fox_pet_backend",
                "port": PORT,
                "autostart": is_autostart_enabled(),
                "config": cfg,
                "expressions": VALID_EXPRESSIONS,
                "expr_titles": EXPR_TITLES,
            })
            return

        if self.path in ("/", "/pet", "/index.html") or self.path.startswith("/pet?") or ".html" in self.path:
            if os.path.exists(HTML_FILE):
                with open(HTML_FILE, "rb") as f:
                    raw = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body_raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body_raw)
        except Exception:
            payload = {}

        if self.path == "/api/fetch_models":
            self.handle_fetch_models(payload)
        elif self.path == "/api/test_llm":
            self.handle_test_llm(payload)
        elif self.path == "/api/chat":
            self.handle_chat(payload)
        elif self.path == "/api/desktop_chat":
            self.handle_desktop_chat(payload)
        elif self.path == "/api/mvu_judge":
            self.handle_mvu_judge(payload)
        elif self.path == "/api/save_config":
            cfg = save_config(payload)
            self._send_json({"ok": True, "config": cfg})
        elif self.path == "/api/set_expression":
            expr = str(payload.get("expression", "expr1")).lower().strip()
            if expr not in VALID_EXPRESSIONS:
                expr = "expr1"
            cfg = save_config({"current_expression": expr, "last_mvu_code": f'<<mvu:set_expr("{expr}")>>'})
            self._send_json({"ok": True, "expression": expr, "title": EXPR_TITLES.get(expr, expr), "config": cfg})
        elif self.path == "/api/browse_app":
            self.handle_browse_app()
        elif self.path == "/api/launch_bound_app":
            self.handle_launch_bound_app(payload)
        elif self.path == "/api/trigger_power":
            self.handle_trigger_power()
        elif self.path == "/api/cancel_power":
            self.handle_cancel_power()
        elif self.path == "/api/speak_sync":
            dur = float(payload.get("duration", 3.2))
            txt = str(payload.get("text", "")).strip()
            upd = {"speak_until_ts": time.time() + max(1.2, min(15.0, dur))}
            if txt:
                upd["last_reply"] = txt
            cfg = save_config(upd)
            self._send_json({"ok": True, "speak_until_ts": cfg.get("speak_until_ts", 0.0)})
        elif self.path == "/api/autostart":
            en = bool(payload.get("enable", True))
            cur = set_autostart(en)
            self._send_json({"ok": True, "autostart": cur})
        else:
            self._send_json({"ok": False, "error": f"Unknown endpoint: {self.path}"}, 404)

    def handle_browse_app(self):
        """Opens native Windows file picker to select an application (.exe / .lnk / .bat) for the Fox Tail."""
        try:
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.OpenFileDialog; "
                "$f.Title = 'Select an App or Shortcut to Bind to the Little White Fox Tail'; "
                "$f.Filter = 'Applications & Shortcuts (*.exe;*.lnk;*.bat;*.cmd;*.url)|*.exe;*.lnk;*.bat;*.cmd;*.url|All Files (*.*)|*.*'; "
                "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.FileName }"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Sta", "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=0x08000000,
                timeout=120,
            )
            chosen = (res.stdout or "").strip()
            if chosen and os.path.exists(chosen):
                bname = os.path.splitext(os.path.basename(chosen))[0]
                cfg = save_config({"bound_app_path": chosen, "bound_app_name": bname})
                self._send_json({"ok": True, "path": chosen, "name": bname, "config": cfg})
                return
            self._send_json({"ok": False, "cancelled": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)})

    def handle_launch_bound_app(self, payload: dict):
        cfg = load_config()
        app_path = (payload.get("bound_app_path") or cfg.get("bound_app_path") or "").strip()
        if not app_path:
            self._send_json({"ok": False, "error": "No application bound yet. Please select an app or URL first."})
            return
        try:
            if app_path.startswith("http://") or app_path.startswith("https://"):
                import webbrowser
                webbrowser.open(app_path)
            elif os.path.exists(app_path):
                os.startfile(app_path)
            else:
                subprocess.Popen(app_path, shell=True, creationflags=0x08000000)
            bname = cfg.get("bound_app_name") or os.path.splitext(os.path.basename(app_path))[0] or app_path
            save_config({"current_expression": "expr4", "last_mvu_code": '<<mvu:set_expr("expr4")>>'})
            self._send_json({"ok": True, "launched": app_path, "name": bname})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)})

    def handle_mvu_judge(self, payload: dict):
        cfg = load_config()
        base_url = normalize_base_url(payload.get("base_url") or cfg.get("base_url", ""))
        api_key = (payload.get("api_key") or cfg.get("api_key", "")).strip()
        model = (payload.get("model") or cfg.get("model", "")).strip()
        user_msg = (payload.get("user_msg") or "").strip()
        bot_reply = (payload.get("bot_reply") or "").strip()
        mvu_sys = (payload.get("mvu_system_prompt") or cfg.get("mvu_system_prompt") or DEFAULT_MVU_SYSTEM_PROMPT).strip()

        expr_id, mvu_code = call_channel2_mvu_api(base_url, api_key, model, user_msg, bot_reply, mvu_sys)
        save_config({"current_expression": expr_id, "last_mvu_code": mvu_code})
        self._send_json({"ok": True, "expression": expr_id, "title": EXPR_TITLES.get(expr_id, expr_id), "mvu_code": mvu_code})

    def handle_desktop_chat(self, payload: dict):
        user_msg = (payload.get("message") or "").strip()
        if not user_msg:
            self._send_json({"ok": False, "error": "Empty message"}, 400)
            return

        cfg = load_config()
        base_url = normalize_base_url(payload.get("base_url") or cfg.get("base_url", ""))
        api_key = (payload.get("api_key") or cfg.get("api_key", "")).strip()
        model = (payload.get("model") or cfg.get("model", "")).strip()
        sys_prompt = sanitize_system_prompt(cfg.get("system_prompt") or DEFAULT_CONFIG["system_prompt"])
        if "character count" not in sys_prompt.lower():
            sys_prompt += " Never output character counts or metadata tags."
        mvu_sys = (cfg.get("mvu_system_prompt") or DEFAULT_MVU_SYSTEM_PROMPT).strip()

        clean_reply = ""
        if base_url and model and (api_key or "127.0.0.1" in base_url or "localhost" in base_url):
            headers = build_headers(api_key)
            req_body = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": float(cfg.get("temperature", 0.78)),
            }).encode("utf-8")

            for url in [f"{base_url}/v1/chat/completions", f"{base_url}/chat/completions"]:
                try:
                    req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=22) as resp:
                        raw = resp.read().decode("utf-8", errors="replace")
                        data = json.loads(raw)
                        if isinstance(data.get("choices"), list) and data["choices"]:
                            raw_reply = (data["choices"][0].get("message") or {}).get("content") or ""
                            clean_reply = strip_any_mvu_tags(raw_reply)
                            break
                except Exception:
                    pass

        if not clean_reply:
            clean_reply = local_contextual_reply(user_msg)

        expr_id, mvu_code = regex_parse_mvu_code("", user_msg + " " + clean_reply)
        spk_dur = max(2.2, min(10.0, len(clean_reply) * 0.08))
        chat_id = int(cfg.get("last_desktop_chat_id") or 0) + 1
        save_config({
            "current_expression": expr_id,
            "last_mvu_code": mvu_code,
            "last_reply": clean_reply,
            "last_desktop_chat_id": chat_id,
            "last_desktop_user_msg": user_msg,
            "last_desktop_reply": clean_reply,
            "speak_until_ts": time.time() + spk_dur,
        })

        def _async_mvu():
            try:
                e2, c2 = call_channel2_mvu_api(base_url, api_key, model, user_msg, clean_reply, mvu_sys)
                if e2 in VALID_EXPRESSIONS:
                    save_config({"current_expression": e2, "last_mvu_code": c2})
            except Exception:
                pass

        threading.Thread(target=_async_mvu, daemon=True).start()

        self._send_json({
            "ok": True,
            "reply": clean_reply,
            "expression": expr_id,
            "title": EXPR_TITLES.get(expr_id, expr_id),
            "mvu_code": mvu_code,
        })

    def handle_chat(self, payload: dict):
        cfg = load_config()
        base_url = normalize_base_url(payload.get("base_url") or cfg.get("base_url", ""))
        api_key = (payload.get("api_key") if "api_key" in payload else cfg.get("api_key", "")).strip()
        model = (payload.get("model") or cfg.get("model", "")).strip()
        messages = list(payload.get("messages") or [])
        temperature = float(payload.get("temperature", cfg.get("temperature", 0.75)))
        mvu_sys = (payload.get("mvu_system_prompt") or cfg.get("mvu_system_prompt") or DEFAULT_MVU_SYSTEM_PROMPT).strip()

        for m in messages:
            if isinstance(m, dict) and m.get("role") == "system" and isinstance(m.get("content"), str):
                sc = sanitize_system_prompt(m["content"])
                if "character count" not in sc.lower():
                    sc += " Never output character counts or metadata tags."
                m["content"] = sc

        save_config({"base_url": base_url, "api_key": api_key, "model": model, "temperature": temperature, "mvu_system_prompt": mvu_sys})

        user_last = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_last = m.get("content", "")
                break

        if base_url and model and (api_key or "127.0.0.1" in base_url or "localhost" in base_url):
            candidate_urls = [
                f"{base_url}/v1/chat/completions",
                f"{base_url}/chat/completions",
            ]
            headers = build_headers(api_key)
            req_body = json.dumps({
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }).encode("utf-8")

            last_err = ""
            for url in candidate_urls:
                try:
                    req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        raw = resp.read().decode("utf-8", errors="replace")
                        data = json.loads(raw)
                        if isinstance(data.get("choices"), list) and data["choices"]:
                            msg = data["choices"][0].get("message") or {}
                            raw_content = msg.get("content") or ""
                            clean_text = strip_any_mvu_tags(raw_content)
                            msg["content"] = clean_text

                            expr_id, mvu_code = regex_parse_mvu_code("", user_last + " " + clean_text)
                            data["mvu_expression"] = expr_id
                            data["mvu_title"] = EXPR_TITLES.get(expr_id, expr_id)
                            data["mvu_code"] = mvu_code
                            spk_dur = max(2.2, min(10.0, len(clean_text) * 0.08))
                            save_config({"current_expression": expr_id, "last_mvu_code": mvu_code, "last_reply": clean_text, "speak_until_ts": time.time() + spk_dur})

                            def _async_mvu_web():
                                try:
                                    e2, c2 = call_channel2_mvu_api(base_url, api_key, model, user_last, clean_text, mvu_sys)
                                    if e2 in VALID_EXPRESSIONS:
                                        save_config({"current_expression": e2, "last_mvu_code": c2})
                                except Exception:
                                    pass

                            threading.Thread(target=_async_mvu_web, daemon=True).start()
                        self._send_json({"ok": True, "data": data})
                        return
                except urllib.error.HTTPError as e:
                    err_body = ""
                    try:
                        err_body = e.read().decode("utf-8", errors="replace")[:240]
                    except Exception:
                        pass
                    last_err = f"HTTP {e.code}: {err_body}"
                except Exception as e:
                    last_err = str(e)

        fallback_reply = local_contextual_reply(user_last)
        expr_id, mvu_code = regex_parse_mvu_code("", user_last + " " + fallback_reply)
        spk_dur = max(1.8, min(10.0, len(fallback_reply) * 0.08))
        save_config({"current_expression": expr_id, "last_mvu_code": mvu_code, "last_reply": fallback_reply, "speak_until_ts": time.time() + spk_dur})
        self._send_json({
            "ok": True,
            "local_fallback": True,
            "data": {
                "choices": [{"message": {"role": "assistant", "content": fallback_reply}}],
                "mvu_expression": expr_id,
                "mvu_title": EXPR_TITLES.get(expr_id, expr_id),
                "mvu_code": mvu_code,
            },
        })

    def handle_fetch_models(self, payload: dict):
        base_url = normalize_base_url(payload.get("base_url", ""))
        api_key = payload.get("api_key", "")
        if not base_url:
            self._send_json({"ok": False, "error": "Please enter an API URL Endpoint first."}, 400)
            return

        save_config({"base_url": base_url, "api_key": api_key})

        candidate_urls = [
            f"{base_url}/v1/models",
            f"{base_url}/models",
            f"{base_url}/api/tags",
        ]
        headers = build_headers(api_key)
        last_err = ""
        t0 = time.time()

        for url in candidate_urls:
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=12) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    data = json.loads(raw)
                    models = []
                    if isinstance(data, dict):
                        if isinstance(data.get("data"), list):
                            for item in data["data"]:
                                if isinstance(item, dict) and item.get("id"):
                                    models.append(str(item["id"]))
                                elif isinstance(item, str):
                                    models.append(item)
                        elif isinstance(data.get("models"), list):
                            for item in data["models"]:
                                if isinstance(item, dict):
                                    m_id = item.get("name") or item.get("id") or item.get("model")
                                    if m_id:
                                        models.append(str(m_id))
                                elif isinstance(item, str):
                                    models.append(item)
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get("id"):
                                models.append(str(item["id"]))
                            elif isinstance(item, str):
                                models.append(item)

                    if models:
                        seen = set()
                        dedup = []
                        for m in models:
                            if m not in seen:
                                seen.add(m)
                                dedup.append(m)
                        ms = int((time.time() - t0) * 1000)
                        self._send_json({
                            "ok": True,
                            "models": dedup,
                            "count": len(dedup),
                            "endpoint": url,
                            "latency_ms": ms,
                        })
                        return
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8", errors="replace")[:200]
                except Exception:
                    pass
                last_err = f"HTTP {e.code} ({url}): {err_body}"
            except Exception as e:
                last_err = f"{url}: {str(e)}"

        self._send_json({"ok": False, "error": f"Failed to fetch model list: {last_err}"}, 200)

    def handle_test_llm(self, payload: dict):
        base_url = normalize_base_url(payload.get("base_url", ""))
        api_key = payload.get("api_key", "")
        model = (payload.get("model") or "").strip()
        if not base_url or not model:
            self._send_json({"ok": False, "error": "Please enter both an API URL Endpoint and a Model Name."}, 200)
            return

        save_config({"base_url": base_url, "api_key": api_key, "model": model})

        candidate_urls = [
            f"{base_url}/v1/chat/completions",
            f"{base_url}/chat/completions",
        ]
        headers = build_headers(api_key)
        req_body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
            "temperature": 0.1,
        }).encode("utf-8")

        last_err = ""
        for url in candidate_urls:
            t0 = time.time()
            try:
                req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    data = json.loads(raw)
                    ms = int((time.time() - t0) * 1000)
                    reply = ""
                    if isinstance(data.get("choices"), list) and data["choices"]:
                        msg = data["choices"][0].get("message") or {}
                        reply = (msg.get("content") or "").strip()
                    self._send_json({
                        "ok": True,
                        "latency_ms": ms,
                        "endpoint": url,
                        "model": model,
                        "sample": reply[:40],
                    })
                    return
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8", errors="replace")[:200]
                except Exception:
                    pass
                last_err = f"HTTP {e.code}: {err_body}"
            except Exception as e:
                last_err = str(e)

        self._send_json({"ok": False, "error": f"Connection failed: {last_err}"}, 200)

    def handle_trigger_power(self):
        mode = random.choice(["shutdown", "restart"])
        flag = "/s" if mode == "shutdown" else "/r"
        label = "Shutdown" if mode == "shutdown" else "Restart"
        comment = f"Shrine Maiden's Divine Punishment: System will {label} in 20 seconds! (Click the green [I'm sorry!] button to abort!)"
        try:
            subprocess.run(["shutdown", flag, "/t", "20", "/c", comment], check=False, creationflags=0x08000000)
            self._send_json({"ok": True, "mode": mode, "label": label, "seconds": 20})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 200)

    def handle_cancel_power(self):
        try:
            subprocess.run(["shutdown", "/a"], check=False, creationflags=0x08000000)
            self._send_json({"ok": True, "cancelled": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 200)


PetBackendHandler = MikoPetBackendHandler

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), MikoPetBackendHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
