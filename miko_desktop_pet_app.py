# -*- coding: utf-8 -*-
"""
Shrine Maiden & Little White Fox (Hidzuki) — 2D Live AI Desktop Companion (English Edition)
Features:
1. Borderless, 100% transparent character + little white fox standing at the bottom-right corner of the Windows desktop.
2. Default Idle State:
   - Bamboo broom and Little White Fox's tail remain stationary by default.
   - Gentle chest/shoulder breathing, natural blinking, and 30 FPS real-time global mouse tracking (`user32.GetCursorPos`)
     driving her full-oval eyeballs (`expr1..expr9_iris.png`) across all open-eye Diffusion expressions!
3. Desktop Physical Interaction 1 — Drag & Drop any file onto her/broom -> Sweeps broom 2 times + plays authentic
   bamboo broom sound (`bamboo_sweep_2x.wav`) + moves file safely into Windows Recycle Bin!
4. Desktop Physical Interaction 2 — Click Little White Fox's tail -> Wags tail 2 times + switches to `④ Loving Heart Eyes` +
   launches the user's bound application (`bound_app_path`).
5. Desktop Physical Interaction 3 — Click Shrine Maiden's chest 5 times -> High-dB `"Kyaa...!"` + Crisp Slap +
   `"Ecchi!"` (`VOICEVOX:Amahare Hau`, with one-click mute toggle) + Crimson 5-Finger Slap Mark + 20s random Shutdown/Restart
   with prominent green `🛑 I'm sorry!! (Abort Shutdown)` button!
6. Click the floating `💬 Talk` button (or right-click menu) to toggle the sleek mini chat input bar at her feet, or open the
   3-Box Backend Web Control Center (`http://127.0.0.1:18766/`).
"""
import os
import sys
import re
import json
import time
import math
import struct
import queue
import random
import ctypes
from ctypes import wintypes
import threading
import subprocess
import webbrowser
import urllib.request
import urllib.parse
import winsound
import tkinter as tk
from tkinter import Menu
import numpy as np
from PIL import Image, ImageTk

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(BASE_DIR, "miko_pet_assets")
EXPR_DIR = os.path.join(ASSETS_DIR, "expressions")
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")
CONFIG_FILE = os.path.join(BASE_DIR, "pet_config.json")
BACKEND_URL = "http://127.0.0.1:18766"

STARTUP_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup",
)
STARTUP_VBS = os.path.join(STARTUP_DIR, "MikoFoxDesktopPet_AutoStart.vbs")
PYTHONW_EXE = r"D:\bilibili_animation_study\see-through\venv\Scripts\pythonw.exe"
if not os.path.exists(PYTHONW_EXE):
    PYTHONW_EXE = sys.executable.replace("python.exe", "pythonw.exe")

# Win32 API setup for global cursor tracking, native file drag-and-drop (WM_DROPFILES), and Recycle Bin
user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
kernel32 = ctypes.windll.kernel32

WM_DROPFILES = 0x0233
GWL_WNDPROC = -4
MEM_COMMIT_RESERVE = 0x3000
PAGE_EXECUTE_READWRITE = 0x40

kernel32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.VirtualAlloc.restype = ctypes.c_void_p
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_void_p
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
user32.SetWindowLongPtrW.restype = ctypes.c_void_p
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
shell32.DragQueryFileW.restype = wintypes.UINT
shell32.DragFinish.argtypes = [wintypes.HANDLE]
shell32.DragFinish.restype = None


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("i64Size", ctypes.c_longlong),
        ("i64NumItems", ctypes.c_longlong),
    ]


def query_recycle_bin_state():
    """Returns (num_items, total_bytes) currently in the Windows Recycle Bin."""
    try:
        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        res = shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if res == 0:
            return int(info.i64NumItems), int(info.i64Size)
    except Exception:
        pass
    return -1, -1


def get_global_cursor():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def move_to_recycle_bin(file_path: str) -> bool:
    """Safely moves a file or folder to the Windows Recycle Bin without confirmation popup."""
    FO_DELETE = 3
    FOF_ALLOWUNDO = 0x0040
    FOF_NOCONFIRMATION = 0x0010
    FOF_SILENT = 0x0004
    op = SHFILEOPSTRUCTW()
    op.hwnd = 0
    op.wFunc = FO_DELETE
    op.pFrom = os.path.abspath(file_path) + "\0\0"
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
    res = shell32.SHFileOperationW(ctypes.byref(op))
    return res == 0


def start_backend_thread():
    try:
        sys.path.insert(0, BASE_DIR)
        import miko_pet_backend_server as srv
        from http.server import ThreadingHTTPServer
        os.chdir(BASE_DIR)
        httpd = ThreadingHTTPServer(("127.0.0.1", srv.PORT), srv.MikoPetBackendHandler)
        httpd.serve_forever()
    except Exception:
        pass


def is_autostart_enabled() -> bool:
    return os.path.exists(STARTUP_VBS)


def set_autostart(enable: bool = True):
    os.makedirs(STARTUP_DIR, exist_ok=True)
    if enable:
        if getattr(sys, "frozen", False):
            target_cmd = f'"""{sys.executable}"""'
        else:
            script_path = os.path.abspath(__file__)
            target_cmd = f'"""{PYTHONW_EXE}"" ""{script_path}"""'
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


EXPR_LABELS = {
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

OPEN_EYE_EXPRS = {"expr1", "expr3", "expr4", "expr5", "expr7", "expr8", "expr9"}


class MikoFoxDesktopPetApp:
    # Wide bounding box in 1024x1024 space so broom sweeping left & fox tail wagging right never clip
    CROP_X0, CROP_Y0, CROP_X1, CROP_Y1 = 168, 0, 905, 1020
    HEAD_X0, HEAD_Y0 = 405, 10  # 200x200 head expression patch coordinates in 1024x1024 space
    SWEEP_DUR = 2.40            # Exact 2.4s 2-stroke broom sweep duration
    SWEEP_FRAMES = 36
    FOX_WAG_DUR = 1.40          # Exact 1.4s 2-wag fox tail duration
    FOX_WAG_FRAMES = 24
    IDLE_BREATH_FRAMES = 24
    TRANSPARENT_HEX = "#010203"
    TRANSPARENT_RGB = (1, 2, 3)

    def __init__(self, root):
        self.root = root
        self.root.title("Shrine Maiden & Little White Fox — Hidzuki Desktop Companion")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", self.TRANSPARENT_HEX)
        self.root.configure(bg=self.TRANSPARENT_HEX)

        # Default compact desktop height ~398px (pet_scale = 0.39)
        self.pet_scale = 0.39
        self.setup_dimensions(initial=True)

        # Animation & MVU State
        self.current_expression = "expr1"
        self.expr_revert_t = 0.0
        self.sweep_start_t = -100.0
        self.sweep_until = 0.0
        self.fox_wag_start_t = -100.0
        self.fox_wag_until = 0.0
        self.slap_mark_until = 0.0
        self.miko_speak_until = time.perf_counter() + 2.8
        self._last_synced_reply = ""
        self._last_synced_spk_ts = 0.0
        self.is_blinking = False
        self.next_blink_t = time.perf_counter() + 2.8
        self.chest_clicks = []
        self.power_countdown = 0
        self.power_timer_id = None
        self.last_poll_t = 0.0
        self._bake_generation = 0
        self._ui_queue = queue.SimpleQueue()
        self._drop_slots = []
        self._trampolines = []

        # Audio file paths
        self.wav_kya_combo = os.path.join(AUDIO_DIR, "kya_slap_ecchi_combo.wav")
        self.wav_slap_only = os.path.join(AUDIO_DIR, "crisp_slap_only.wav")
        self.wav_sweep_2x = os.path.join(AUDIO_DIR, "bamboo_sweep_2x.wav")

        # Canvas
        self.canvas = tk.Canvas(
            self.root,
            width=self.win_w,
            height=self.win_h,
            bg=self.TRANSPARENT_HEX,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.img_item = self.canvas.create_image(8, 68, anchor="nw")
        self.tk_img = None

        # Compact Speech Bubble above her head (auto-hides!)
        self.bubble_lbl = tk.Label(
            self.root,
            text="⛩️ Welcome back! Little White Fox and I are right here in your corner♪",
            bg="#1f1624",
            fg="#ffe4e6",
            font=("Segoe UI", 8),
            wraplength=self.win_w - 12,
            justify="left",
            padx=6,
            pady=4,
            bd=1,
            relief="solid",
        )
        self.bubble_lbl.place(x=6, y=2, width=self.win_w - 12)
        self.bubble_lbl.bind("<Button-1>", lambda e: self.hide_bubble())
        self.bubble_hide_after = self.root.after(4500, self.hide_bubble)

        # Floating Green Mercy Button (only shown during 5-click chest slap power penalty)
        self.mercy_btn = tk.Button(
            self.root,
            text="🛑 I'm sorry!! (Abort Shutdown)",
            bg="#10b981",
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=4,
            pady=3,
            cursor="hand2",
            command=self.cancel_power_penalty,
        )

        # Sleek Mini Chat Input Bar at her feet (hidden by default; toggle via Talk button or right-click menu)
        self.chat_frame = tk.Frame(self.root, bg="#1f1624", bd=1, relief="solid", highlightbackground="#f43f5e", highlightthickness=1)
        self.chat_send_btn = tk.Button(
            self.chat_frame,
            text="Send",
            bg="#e11d48",
            fg="#ffffff",
            activebackground="#be185d",
            activeforeground="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=8,
            pady=1,
            cursor="hand2",
            command=self.on_send_mini_chat,
        )
        self.chat_send_btn.pack(side="right", fill="y", padx=2, pady=2)
        self.chat_entry = tk.Entry(
            self.chat_frame,
            bg="#1f1624",
            fg="#fff1f2",
            insertbackground="#fda4af",
            font=("Segoe UI", 9),
            bd=0,
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=5, pady=3)
        self.chat_entry.bind("<Return>", self.on_send_mini_chat)
        self.chat_entry.bind("<KP_Enter>", self.on_send_mini_chat)
        self.chat_entry.bind("<Escape>", lambda e: self.toggle_chat_bar(False))
        self.chat_entry.bind("<ButtonPress-1>", lambda e: self.root.after(5, self.focus_chat_input))
        self.chat_entry.bind("<ButtonRelease-1>", lambda e: self.root.after(5, self.focus_chat_input))
        self.chat_frame.bind("<ButtonPress-1>", lambda e: self.root.after(5, self.focus_chat_input))
        self.chat_visible = False

        # Compact floating chat toggle button at bottom-right so rapid clicking on her body never conflicts with Double-Button-1
        self.chat_open_btn = tk.Button(
            self.root,
            text="💬 Talk",
            bg="#1f1624",
            fg="#fda4af",
            activebackground="#e11d48",
            activeforeground="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=1,
            relief="solid",
            padx=6,
            pady=1,
            cursor="hand2",
            command=self.toggle_chat_bar,
        )
        self.chat_open_btn.place(x=self.win_w - 64, y=self.win_h - 26, width=58, height=22)

        # Build Right-Click Context Menu
        self.build_context_menu()

        # Load and pre-scale layers for <1.5ms 30 FPS real-time mouse-tracking rendering
        self.load_and_group_layers()

        # Mouse bindings (NO <Double-Button-1> on canvas so 5-click chest poking never triggers chat bar or focus conflicts!)
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.press_x_root = 0
        self.press_y_root = 0
        self.drag_moved = False
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # Register native Windows file drag-and-drop (WM_DROPFILES -> Broom sweeps file into Recycle Bin!)
        self.root.after(200, self.register_native_file_drop)

        # Start 30 FPS 2D Live loop
        self.animate()

    def setup_dimensions(self, initial=False):
        self.cw = int(round((self.CROP_X1 - self.CROP_X0) * self.pet_scale))
        self.ch = int(round((self.CROP_Y1 - self.CROP_Y0) * self.pet_scale))
        self.win_w = max(220, self.cw + 16)
        self.win_h = self.ch + 98
        scr_w = self.root.winfo_screenwidth()
        scr_h = self.root.winfo_screenheight()
        if initial:
            init_x = scr_w - self.win_w - 18
            init_y = scr_h - self.win_h - 46
            self.root.geometry(f"{self.win_w}x{self.win_h}+{init_x}+{init_y}")
        else:
            cur_x = min(scr_w - self.win_w - 10, max(10, self.root.winfo_x()))
            cur_y = min(scr_h - self.win_h - 40, max(10, self.root.winfo_y()))
            self.root.geometry(f"{self.win_w}x{self.win_h}+{cur_x}+{cur_y}")
            self.canvas.config(width=self.win_w, height=self.win_h)
            if hasattr(self, "chat_open_btn") and not self.chat_visible:
                self.chat_open_btn.place(x=self.win_w - 64, y=self.win_h - 26, width=58, height=22)

    def read_local_config(self) -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def build_context_menu(self):
        self.menu = Menu(self.root, tearoff=0, bg="#1f1624", fg="#fff1f2", font=("Segoe UI", 9))
        self.menu.add_command(label="💬 Talk to Hidzuki", command=self.toggle_chat_bar)
        self.menu.add_command(label="⚙️ Open Web Control Panel", command=self.open_backend_web)
        self.menu.add_separator()
        self.menu.add_command(label="🦊 Bind App to Fox Tail", command=self.bind_fox_tail_app)
        self.menu.add_command(label="🧹 Sweep with Bamboo Broom", command=self.trigger_broom_demo)

        cfg = self.read_local_config()
        self.builtin_voice_var = tk.BooleanVar(value=cfg.get("builtin_voice_enabled", True))
        self.menu.add_checkbutton(
            label='🔊 Built-in Bonus Voice ("Kyaa...! Ecchi!" 1 line only)',
            variable=self.builtin_voice_var,
            command=self.toggle_builtin_voice,
        )

        # Submenu for all 9 expressions
        self.expr_menu = Menu(self.menu, tearoff=0, bg="#1f1624", fg="#fff1f2", font=("Segoe UI", 9))
        for expr_id, label in EXPR_LABELS.items():
            self.expr_menu.add_command(
                label=label,
                command=lambda eid=expr_id: self.set_mvu_expression(eid, announce=True),
            )
        self.menu.add_cascade(label="🎭 Switch Expression (All 9)", menu=self.expr_menu)

        # Submenu for adjusting desktop pet size
        self.size_menu = Menu(self.menu, tearoff=0, bg="#1f1624", fg="#fff1f2", font=("Segoe UI", 9))
        self.size_menu.add_command(label="Small", command=lambda: self.change_scale(0.34))
        self.size_menu.add_command(label="Standard (Default)", command=lambda: self.change_scale(0.39))
        self.size_menu.add_command(label="Large", command=lambda: self.change_scale(0.45))
        self.menu.add_cascade(label="🔍 Change Size", menu=self.size_menu)

        self.menu.add_separator()
        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        self.menu.add_checkbutton(
            label="🚀 Run at Windows Startup",
            variable=self.autostart_var,
            command=self.toggle_autostart,
        )
        self.menu.add_command(label="📌 Snap to Bottom-Right", command=self.snap_to_bottom_right)
        self.menu.add_separator()
        self.menu.add_command(label="❌ Quit", command=self.quit_app)

    def register_native_file_drop(self):
        """
        Hooks Win32 WM_DROPFILES using a pure x64 machine-code trampoline (ZERO _ctypes.WINFUNCTYPE / ZERO Python GIL!)
        so rapid mouse clicks and nested Win32 window messages NEVER trigger Py_FatalError in python310.dll.
        """
        try:
            self.root.update_idletasks()
            hwnd_inner = self.root.winfo_id()
            hwnd_top = user32.GetParent(hwnd_inner) or hwnd_inner
            hwnd_canvas = self.canvas.winfo_id()

            if ctypes.sizeof(ctypes.c_void_p) == 8:
                for h in {hwnd_top, hwnd_inner, hwnd_canvas}:
                    if not h:
                        continue
                    try:
                        shell32.DragAcceptFiles(h, True)
                        old_p = user32.GetWindowLongPtrW(h, GWL_WNDPROC)
                        if not old_p:
                            continue
                        slot = (ctypes.c_uint64 * 1)(0)
                        slot_addr = ctypes.addressof(slot)
                        # x64 Windows ABI: rcx=hwnd, edx=msg, r8=wParam (HDROP), r9=lParam
                        code = (
                            b"\x81\xfa\x33\x02\x00\x00"                  # cmp edx, 0x0233 (WM_DROPFILES)
                            + b"\x74\x0c"                                # je +12 (to handle_drop)
                            + b"\x48\xb8" + struct.pack("<Q", old_p)     # movabs rax, old_p
                            + b"\xff\xe0"                                # jmp rax
                            + b"\x48\xb8" + struct.pack("<Q", slot_addr) # movabs rax, slot_addr
                            + b"\x4c\x89\x00"                            # mov [rax], r8 (store HDROP)
                            + b"\x31\xc0"                                # xor eax, eax (return 0)
                            + b"\xc3"                                    # ret
                        )
                        buf = kernel32.VirtualAlloc(None, 64, MEM_COMMIT_RESERVE, PAGE_EXECUTE_READWRITE)
                        if buf:
                            ctypes.memmove(buf, code, len(code))
                            user32.SetWindowLongPtrW(h, GWL_WNDPROC, buf)
                            self._drop_slots.append(slot)
                            self._trampolines.append(buf)
                    except Exception:
                        pass
        except Exception:
            pass

        # Also start background Recycle Bin sensor so dropping a file into the Recycle Bin next to her broom triggers 2x sweep!
        threading.Thread(target=self._recycle_bin_watcher_loop, daemon=True).start()

    def _recycle_bin_watcher_loop(self):
        last_items, last_size = query_recycle_bin_state()
        self._last_rb_items = last_items
        self._last_rb_size = last_size
        while True:
            time.sleep(0.45)
            cur_items, cur_size = query_recycle_bin_state()
            if cur_items < 0:
                continue
            if self._last_rb_items >= 0 and (
                cur_items > self._last_rb_items
                or (cur_items == self._last_rb_items and cur_size > self._last_rb_size and cur_items > 0)
            ):
                if time.perf_counter() >= self.sweep_until:
                    self._ui_queue.put(self._trigger_recycle_bin_detected_sweep)
            self._last_rb_items = cur_items
            self._last_rb_size = cur_size

    def _trigger_recycle_bin_detected_sweep(self):
        now = time.perf_counter()
        if now < self.sweep_until:
            return
        self.sweep_start_t = now
        self.sweep_until = now + self.SWEEP_DUR
        self.expr_revert_t = self.sweep_until + 0.55
        self.set_mvu_expression("expr3", announce=False)
        if os.path.exists(self.wav_sweep_2x):
            winsound.PlaySound(self.wav_sweep_2x, winsound.SND_FILENAME | winsound.SND_ASYNC)
        self.show_bubble("🧹 (Swish, swish...!) Swept nicely into the Recycle Bin♪ ✨", 4500)

    def handle_wm_dropfiles(self, hdrop):
        try:
            # 1. Immediately trigger the 2-stroke 64x64 mesh broom sweep animation + bamboo broom sound!
            self.sweep_start_t = time.perf_counter()
            self.sweep_until = self.sweep_start_t + self.SWEEP_DUR
            self.expr_revert_t = self.sweep_until + 0.55
            self.set_mvu_expression("expr3", announce=False)
            if os.path.exists(self.wav_sweep_2x):
                winsound.PlaySound(self.wav_sweep_2x, winsound.SND_FILENAME | winsound.SND_ASYNC)

            # 2. Extract dropped file paths and finish HDROP handle (64-bit safe)
            count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
            dropped_paths = []
            buf = ctypes.create_unicode_buffer(1024)
            for i in range(count):
                shell32.DragQueryFileW(hdrop, i, buf, 1024)
                fpath = buf.value
                if fpath and os.path.exists(fpath):
                    dropped_paths.append(fpath)
            try:
                shell32.DragFinish(hdrop)
            except Exception:
                pass

            if dropped_paths:
                bnames = [os.path.basename(p) for p in dropped_paths]
                joined = ", ".join(bnames[:2]) + (f" (+{len(bnames) - 2} more)" if len(bnames) > 2 else "")
                self.show_bubble(f'🧹 (Swish, swish...!) Swept "{joined}" into the Recycle Bin♪ ✨', 4500)

                def _recycle_worker(paths):
                    for p in paths:
                        try:
                            move_to_recycle_bin(p)
                        except Exception:
                            pass
                    c_items, c_size = query_recycle_bin_state()
                    if c_items >= 0:
                        self._last_rb_items = c_items
                        self._last_rb_size = c_size

                threading.Thread(target=_recycle_worker, args=(dropped_paths,), daemon=True).start()
        except Exception:
            pass

    def load_cropped_layer(self, filename: str) -> Image.Image:
        p = os.path.join(ASSETS_DIR, filename)
        if not os.path.exists(p):
            return Image.new("RGBA", (self.cw, self.ch), (0, 0, 0, 0))
        im = Image.open(p).convert("RGBA").crop((self.CROP_X0, self.CROP_Y0, self.CROP_X1, self.CROP_Y1))
        return im.resize((self.cw, self.ch), Image.Resampling.LANCZOS)

    def load_head_patch(self, filename: str) -> Image.Image:
        p = os.path.join(EXPR_DIR, filename)
        if not os.path.exists(p):
            return Image.new("RGBA", (self.hw, self.hh), (0, 0, 0, 0))
        im = Image.open(p).convert("RGBA")
        return im.resize((self.hw, self.hh), Image.Resampling.LANCZOS)

    @staticmethod
    def _smoothstep_arr(v: np.ndarray) -> np.ndarray:
        return v * v * (3.0 - 2.0 * v)

    @staticmethod
    def _broom_disp_scalar(x: float, y: float, dx_pivot: float, dy_pivot: float, shear_k: float, bristle_lag: float):
        ry = y - 285.0
        rx = x - 542.0
        dx = dx_pivot + shear_k * ry
        dy = dy_pivot - shear_k * rx * 0.45
        wb = max(0.0, min(1.0, (y - 650.0) / 315.0)) ** 1.65
        dx -= bristle_lag * wb
        dy -= abs(bristle_lag) * 0.12 * wb
        return dx, dy

    @staticmethod
    def _broom_disp_grid(X: np.ndarray, Y: np.ndarray, dx_pivot: float, dy_pivot: float, shear_k: float, bristle_lag: float):
        ry = Y - 285.0
        rx = X - 542.0
        dx = dx_pivot + shear_k * ry
        dy = dy_pivot - shear_k * rx * 0.45
        wb = np.clip((Y - 650.0) / 315.0, 0.0, 1.0) ** 1.65
        dx = dx - bristle_lag * wb
        dy = dy - abs(bristle_lag) * 0.12 * wb
        return dx, dy

    def _warp_roi_into_canvas(self, canvas_im: Image.Image, key: str, dx_roi: np.ndarray, dy_roi: np.ndarray):
        src_f32 = self._f32_layers[key]
        y0_r, y1_r, x0_r, x1_r, px_r, py_r, _, _ = self._layer_rois[key]
        sx = px_r - dx_roi * self.pet_scale
        sy = py_r - dy_roi * self.pet_scale
        h, w, _ = src_f32.shape
        valid = (sx >= 0.0) & (sx < w - 1.001) & (sy >= 0.0) & (sy < h - 1.001)
        sx_c = np.clip(sx, 0.0, w - 1.001)
        sy_c = np.clip(sy, 0.0, h - 1.001)
        ix = sx_c.astype(np.intp)
        iy = sy_c.astype(np.intp)
        wx = (sx_c - ix)[:, :, None]
        wy = (sy_c - iy)[:, :, None]
        p00 = src_f32[iy, ix]
        p10 = src_f32[iy, ix + 1]
        p01 = src_f32[iy + 1, ix]
        p11 = src_f32[iy + 1, ix + 1]
        res = (p00 * (1.0 - wx) + p10 * wx) * (1.0 - wy) + (p01 * (1.0 - wx) + p11 * wx) * wy
        res[:, :, 3] *= valid
        patch = Image.fromarray(np.clip(res, 0, 255).astype(np.uint8))
        canvas_im.alpha_composite(patch, dest=(x0_r, y0_r))

    def load_and_group_layers(self):
        """Pre-scales layers and builds the 64x64 mesh deformation engine for sweeping & tail wagging."""
        self._bake_generation += 1

        self.hx = int(round((self.HEAD_X0 - self.CROP_X0) * self.pet_scale))
        self.hy = int(round((self.HEAD_Y0 - self.CROP_Y0) * self.pet_scale))
        self.hw = int(round(200 * self.pet_scale))
        self.hh = int(round(200 * self.pet_scale))

        self.lyr_back_hair = self.load_cropped_layer("01_back_hair.png")
        self.lyr_cords_hw = self.load_cropped_layer("02_cords_headwear.png")
        self.lyr_feet = self.load_cropped_layer("03_feet.png")
        self.lyr_torso_skirt = self.load_cropped_layer("04_torso_skirt.png")
        self.lyr_broom = self.load_cropped_layer("05_broom.png")
        self.lyr_sleeve_l = self.load_cropped_layer("06_sleeve_l.png")
        self.lyr_sleeve_r = self.load_cropped_layer("07_sleeve_r.png")
        self.lyr_broom_top = self.load_cropped_layer("08_broom_top.png")
        self.lyr_fox_tail = self.load_cropped_layer("10_fox_tail.png")
        self.lyr_fox_body = self.load_cropped_layer("11_fox_body.png")
        self.lyr_slap_mark = self.load_cropped_layer("12_slap_mark.png")

        # Pre-load all 9 Diffusion expressions (sclera, movable full-oval iris, frame) + blink + open mouth
        self.expr_sclera = {}
        self.expr_iris = {}
        self.expr_frame = {}
        for expr_id in EXPR_LABELS:
            self.expr_sclera[expr_id] = self.load_head_patch(f"{expr_id}_sclera.png")
            self.expr_iris[expr_id] = self.load_head_patch(f"{expr_id}_iris.png")
            self.expr_frame[expr_id] = self.load_head_patch(f"{expr_id}_frame.png")

        self.patch_closed_eyes = self.load_head_patch("closed_eyes_200.png")
        self.patch_mouth_closed = self.load_head_patch("mouth_closed_200.png")
        self.patch_mouth_half = self.load_head_patch("mouth_half_200.png")
        self.patch_mouth_open = self.load_head_patch("mouth_open_200.png")

        # Build float32 arrays and ROI coordinate slices in 1024x1024 space for exact mesh deformation
        py_grid, px_grid = np.indices((self.ch, self.cw), dtype=np.float32)
        X_1024 = self.CROP_X0 + px_grid / self.pet_scale
        Y_1024 = self.CROP_Y0 + py_grid / self.pet_scale

        self._f32_layers = {
            "back_hair": np.array(self.lyr_back_hair, dtype=np.float32),
            "cords": np.array(self.lyr_cords_hw, dtype=np.float32),
            "torso": np.array(self.lyr_torso_skirt, dtype=np.float32),
            "broom": np.array(self.lyr_broom, dtype=np.float32),
            "sleeve_l": np.array(self.lyr_sleeve_l, dtype=np.float32),
            "sleeve_r": np.array(self.lyr_sleeve_r, dtype=np.float32),
            "broom_top": np.array(self.lyr_broom_top, dtype=np.float32),
            "fox_tail": np.array(self.lyr_fox_tail, dtype=np.float32),
            "fox_body": np.array(self.lyr_fox_body, dtype=np.float32),
        }
        self._layer_rois = {}
        for k, arr in self._f32_layers.items():
            ys, xs = np.where(arr[:, :, 3] > 1)
            if len(ys) == 0:
                y0_r, y1_r, x0_r, x1_r = 0, self.ch, 0, self.cw
            else:
                y0_r = max(0, int(ys.min()) - 22)
                y1_r = min(self.ch, int(ys.max()) + 22)
                x0_r = max(0, int(xs.min()) - 56)
                x1_r = min(self.cw, int(xs.max()) + 56)
            self._layer_rois[k] = (
                y0_r,
                y1_r,
                x0_r,
                x1_r,
                px_grid[y0_r:y1_r, x0_r:x1_r],
                py_grid[y0_r:y1_r, x0_r:x1_r],
                X_1024[y0_r:y1_r, x0_r:x1_r],
                Y_1024[y0_r:y1_r, x0_r:x1_r],
            )

        # Precompute exact vertex weights per ROI
        _, _, _, _, _, _, _, Y_bh = self._layer_rois["back_hair"]
        self._wHair_bh = np.clip((Y_bh - 230.0) / 300.0, 0.0, 1.0) ** 1.4

        _, _, _, _, _, _, X_c, Y_c = self._layer_rois["cords"]
        self._c_is_upper = Y_c < 230.0
        self._c_is_right = X_c < 495.0
        self._wArm_r_c = self._smoothstep_arr(np.clip((Y_c - 225.0) / (385.0 - 225.0), 0.0, 1.0))
        self._wPouch_r_c = np.clip((Y_c - 410.0) / 215.0, 0.0, 1.0) ** 1.35
        self._wArm_l_c = self._smoothstep_arr(np.clip((Y_c - 220.0) / (305.0 - 220.0), 0.0, 1.0))
        self._wPouch_l_c = np.clip((Y_c - 360.0) / 265.0, 0.0, 1.0) ** 1.35
        self._c_cdx = X_c - 495.0
        self._c_cdy = Y_c - 246.0
        self._wChest_c = (
            np.exp(-(self._c_cdx ** 2 / (2.0 * 64.0 ** 2) + self._c_cdy ** 2 / (2.0 * 44.0 ** 2)))
            * self._smoothstep_arr(np.clip((Y_c - 202.0) / 24.0, 0.0, 1.0))
        )

        _, _, _, _, _, _, X_t, Y_t = self._layer_rois["torso"]
        self._t_cdx = X_t - 495.0
        self._t_cdy = Y_t - 246.0
        self._wChest_t = (
            np.exp(-(self._t_cdx ** 2 / (2.0 * 58.0 ** 2) + self._t_cdy ** 2 / (2.0 * 44.0 ** 2)))
            * self._smoothstep_arr(np.clip((Y_t - 202.0) / 24.0, 0.0, 1.0))
            * self._smoothstep_arr(np.clip((345.0 - Y_t) / 45.0, 0.0, 1.0))
        )

        _, _, _, _, _, _, X_sl, Y_sl = self._layer_rois["sleeve_l"]
        self._wArm_sl = self._smoothstep_arr(np.clip((Y_sl - 220.0) / (305.0 - 220.0), 0.0, 1.0))
        self._wPouch_sl = np.clip((Y_sl - 360.0) / 265.0, 0.0, 1.0) ** 1.35
        self._wChest_sl = (
            np.exp(-((X_sl - 535.0) ** 2 / (2.0 * 52.0 ** 2) + (Y_sl - 248.0) ** 2 / (2.0 * 42.0 ** 2)))
            * self._smoothstep_arr(np.clip((Y_sl - 205.0) / 22.0, 0.0, 1.0))
        )

        _, _, _, _, _, _, X_sr, Y_sr = self._layer_rois["sleeve_r"]
        self._wArm_sr = self._smoothstep_arr(np.clip((Y_sr - 225.0) / (385.0 - 225.0), 0.0, 1.0))
        self._wPouch_sr = np.clip((Y_sr - 410.0) / 215.0, 0.0, 1.0) ** 1.35
        self._wChest_sr = (
            np.exp(-((X_sr - 455.0) ** 2 / (2.0 * 52.0 ** 2) + (Y_sr - 248.0) ** 2 / (2.0 * 42.0 ** 2)))
            * self._smoothstep_arr(np.clip((Y_sr - 205.0) / 22.0, 0.0, 1.0))
        )

        _, _, _, _, _, _, X_ft, Y_ft = self._layer_rois["fox_tail"]
        self._ft_rx = X_ft - 775.3
        self._ft_ry = Y_ft - 908.5
        self._w_tail = np.clip(np.hypot(self._ft_rx, self._ft_ry) / (95.0 * 0.41), 0.0, 1.0) ** 1.15
        self._tipW_tail = np.clip((816.0 - Y_ft) / (280.0 * 0.41), 0.0, 1.0) ** 1.5

        _, _, _, _, _, _, X_fb, Y_fb = self._layer_rois["fox_body"]
        self._fb_cdx = X_fb - 682.0
        self._fb_cdy = Y_fb - 815.0
        self._wChest_fb = (
            np.exp(-(self._fb_cdx ** 2 / (2.0 * 48.0 ** 2) + self._fb_cdy ** 2 / (2.0 * 42.0 ** 2)))
            * self._smoothstep_arr(np.clip((885.0 - Y_fb) / 30.0, 0.0, 1.0))
        )

        # Precompute exact 36-step 2-stroke broom sweep trajectory (u, dragWave)
        self._sweep_traj = []
        prev_u = 0.22
        smooth_vel = 0.0
        for i in range(self.SWEEP_FRAMES):
            prog = i / (self.SWEEP_FRAMES - 1)
            env = math.sin(prog * math.pi)
            wave = math.sin(prog * math.pi * 4.0)
            u = 0.22 + env * (0.32 + 0.42 * wave)
            inst_vel = (u - prev_u) * (self.SWEEP_FRAMES / self.SWEEP_DUR)
            prev_u = u
            smooth_vel += (inst_vel - smooth_vel) * 0.22
            drag_wave = max(-1.5, min(1.5, smooth_vel * 0.85))
            self._sweep_traj.append((u, drag_wave))

        self._idle_static_body = Image.new("RGBA", (self.cw, self.ch), (0, 0, 0, 0))
        self._idle_static_body.alpha_composite(self.lyr_back_hair)
        self._idle_static_body.alpha_composite(self.lyr_cords_hw)
        self._idle_static_body.alpha_composite(self.lyr_feet)
        self._idle_static_body.alpha_composite(self.lyr_torso_skirt)
        self._idle_static_body.alpha_composite(self.lyr_broom)
        self._idle_static_body.alpha_composite(self.lyr_sleeve_l)
        self._idle_static_body.alpha_composite(self.lyr_sleeve_r)
        self._idle_static_body.alpha_composite(self.lyr_broom_top)

        self.idle_breath_frames = [None] * self.IDLE_BREATH_FRAMES
        self.fox_breath_frames = [None] * self.IDLE_BREATH_FRAMES
        self.sweep_body_frames = [None] * self.SWEEP_FRAMES
        self.fox_wag_frames = [None] * self.FOX_WAG_FRAMES
        self._warm_cursor = 0

    def _build_idle_breath_frame(self, idx: int) -> Image.Image:
        phase = (idx / self.IDLE_BREATH_FRAMES) * (2.0 * math.pi)
        breath = math.sin(phase)
        chest_expand = breath * 1.35

        frm = Image.new("RGBA", (self.cw, self.ch), (0, 0, 0, 0))
        frm.alpha_composite(self.lyr_back_hair)

        c_dx = (self._c_cdx / 58.0) * chest_expand * self._wChest_c
        c_dy = -chest_expand * 1.25 * self._wChest_c
        self._warp_roi_into_canvas(frm, "cords", c_dx, c_dy)

        frm.alpha_composite(self.lyr_feet)

        t_dx = (self._t_cdx / 58.0) * chest_expand * self._wChest_t
        t_dy = -chest_expand * 1.30 * self._wChest_t
        self._warp_roi_into_canvas(frm, "torso", t_dx, t_dy)

        frm.alpha_composite(self.lyr_broom)

        sl_dx = (chest_expand * 0.32) * self._wChest_sl
        sl_dy = (-chest_expand * 0.85) * self._wChest_sl
        self._warp_roi_into_canvas(frm, "sleeve_l", sl_dx, sl_dy)

        sr_dx = (-chest_expand * 0.32) * self._wChest_sr
        sr_dy = (-chest_expand * 0.85) * self._wChest_sr
        self._warp_roi_into_canvas(frm, "sleeve_r", sr_dx, sr_dy)

        frm.alpha_composite(self.lyr_broom_top)
        return frm

    def _build_fox_breath_frame(self, idx: int) -> Image.Image:
        phase = (idx / self.IDLE_BREATH_FRAMES) * (2.0 * math.pi) + 0.7
        f_breath = math.sin(phase) * 0.85
        fb_dx = (self._fb_cdx / 52.0) * f_breath * self._wChest_fb
        fb_dy = -f_breath * 0.95 * self._wChest_fb
        frm = Image.new("RGBA", (self.cw, self.ch), (0, 0, 0, 0))
        self._warp_roi_into_canvas(frm, "fox_body", fb_dx, fb_dy)
        return frm

    def _build_sweep_body_frame(self, idx: int) -> Image.Image:
        u, drag_wave = self._sweep_traj[idx]
        s = u - 0.22
        dx_pivot = s * 16.0
        shear_k = s * 0.225
        dy_pivot = 2.5 * abs(s)
        bristle_lag = drag_wave * 19.0

        lh_dx, lh_dy = self._broom_disp_scalar(535.0, 305.0, dx_pivot, dy_pivot, shear_k, bristle_lag)
        rh_dx, rh_dy = self._broom_disp_scalar(495.0, 385.0, dx_pivot, dy_pivot, shear_k, bristle_lag)

        frm = Image.new("RGBA", (self.cw, self.ch), (0, 0, 0, 0))

        bh_dx = (s * 4.5 - drag_wave * 4.5) * self._wHair_bh
        bh_dy = np.zeros_like(bh_dx)
        self._warp_roi_into_canvas(frm, "back_hair", bh_dx, bh_dy)

        c_dx = np.where(
            self._c_is_upper,
            0.0,
            np.where(
                self._c_is_right,
                rh_dx * self._wArm_r_c - drag_wave * 8.5 * self._wPouch_r_c,
                lh_dx * self._wArm_l_c - drag_wave * 7.0 * self._wPouch_l_c,
            ),
        )
        c_dy = np.where(
            self._c_is_upper,
            0.0,
            np.where(self._c_is_right, rh_dy * self._wArm_r_c, lh_dy * self._wArm_l_c),
        )
        self._warp_roi_into_canvas(frm, "cords", c_dx, c_dy)

        frm.alpha_composite(self.lyr_feet)
        frm.alpha_composite(self.lyr_torso_skirt)

        _, _, _, _, _, _, X_b, Y_b = self._layer_rois["broom"]
        bdx1, bdy1 = self._broom_disp_grid(X_b, Y_b, dx_pivot, dy_pivot, shear_k, bristle_lag)
        bdx, bdy = self._broom_disp_grid(X_b - bdx1, Y_b - bdy1, dx_pivot, dy_pivot, shear_k, bristle_lag)
        self._warp_roi_into_canvas(frm, "broom", bdx, bdy)

        sl_dx = lh_dx * self._wArm_sl - drag_wave * 6.5 * self._wPouch_sl
        sl_dy = lh_dy * self._wArm_sl
        self._warp_roi_into_canvas(frm, "sleeve_l", sl_dx, sl_dy)

        sr_dx = rh_dx * self._wArm_sr - drag_wave * 8.0 * self._wPouch_sr
        sr_dy = rh_dy * self._wArm_sr
        self._warp_roi_into_canvas(frm, "sleeve_r", sr_dx, sr_dy)

        _, _, _, _, _, _, X_bt, Y_bt = self._layer_rois["broom_top"]
        btdx1, btdy1 = self._broom_disp_grid(X_bt, Y_bt, dx_pivot, dy_pivot, shear_k, bristle_lag)
        btdx, btdy = self._broom_disp_grid(X_bt - btdx1, Y_bt - btdy1, dx_pivot, dy_pivot, shear_k, bristle_lag)
        self._warp_roi_into_canvas(frm, "broom_top", btdx, btdy)

        return frm

    def _build_fox_wag_frame(self, idx: int) -> Image.Image:
        fp = idx / (self.FOX_WAG_FRAMES - 1)
        env = math.sin(fp * math.pi)
        fox_wag = math.sin(fp * math.pi * 4.0) * env * 1.25
        fox_wag_lag = math.sin(fp * math.pi * 4.0 - 0.55) * env * 1.25
        fox_theta = fox_wag * 14.0 * math.pi / 180.0
        fox_cos = math.cos(fox_theta)
        fox_sin = math.sin(fox_theta)

        _, _, _, _, _, _, X_ft, Y_ft = self._layer_rois["fox_tail"]
        nx = 775.3 + self._ft_rx * fox_cos - self._ft_ry * fox_sin + fox_wag_lag * 6.5 * self._tipW_tail
        ny = 908.5 + self._ft_rx * fox_sin + self._ft_ry * fox_cos
        dx = (nx - X_ft) * self._w_tail
        dy = (ny - Y_ft) * self._w_tail

        frm = Image.new("RGBA", (self.cw, self.ch), (0, 0, 0, 0))
        self._warp_roi_into_canvas(frm, "fox_tail", dx, dy)
        return frm

    def _warm_one_frame_step(self):
        c = getattr(self, "_warm_cursor", 0)
        n1 = self.IDLE_BREATH_FRAMES
        n2 = n1 + self.SWEEP_FRAMES
        n3 = n2 + self.FOX_WAG_FRAMES
        if c >= n3:
            return
        if c < n1:
            if self.idle_breath_frames[c] is None:
                self.idle_breath_frames[c] = self._build_idle_breath_frame(c)
            if self.fox_breath_frames[c] is None:
                self.fox_breath_frames[c] = self._build_fox_breath_frame(c)
        elif c < n2:
            i = c - n1
            if self.sweep_body_frames[i] is None:
                self.sweep_body_frames[i] = self._build_sweep_body_frame(i)
        else:
            j = c - n2
            if self.fox_wag_frames[j] is None:
                self.fox_wag_frames[j] = self._build_fox_wag_frame(j)
        self._warm_cursor = c + 1

    def get_idle_breath_frame(self, idx: int) -> Image.Image:
        idx = idx % self.IDLE_BREATH_FRAMES
        if self.idle_breath_frames[idx] is None:
            self.idle_breath_frames[idx] = self._build_idle_breath_frame(idx)
        return self.idle_breath_frames[idx]

    def get_fox_breath_frame(self, idx: int) -> Image.Image:
        idx = idx % self.IDLE_BREATH_FRAMES
        if self.fox_breath_frames[idx] is None:
            self.fox_breath_frames[idx] = self._build_fox_breath_frame(idx)
        return self.fox_breath_frames[idx]

    def get_sweep_body_frame(self, idx: int) -> Image.Image:
        idx = max(0, min(self.SWEEP_FRAMES - 1, idx))
        if self.sweep_body_frames[idx] is None:
            self.sweep_body_frames[idx] = self._build_sweep_body_frame(idx)
        return self.sweep_body_frames[idx]

    def get_fox_wag_frame(self, idx: int) -> Image.Image:
        idx = max(0, min(self.FOX_WAG_FRAMES - 1, idx))
        if self.fox_wag_frames[idx] is None:
            self.fox_wag_frames[idx] = self._build_fox_wag_frame(idx)
        return self.fox_wag_frames[idx]

    def change_scale(self, new_scale: float):
        self.pet_scale = new_scale
        self.setup_dimensions(initial=False)
        self.load_and_group_layers()
        self.canvas.coords(self.img_item, 8, 68)
        if self.chat_visible:
            self.chat_frame.place(x=6, y=self.win_h - 30, width=self.win_w - 12, height=28)

    @staticmethod
    def paste_offset(dst: Image.Image, src: Image.Image, dx: int = 0, dy: int = 0):
        if dx == 0 and dy == 0:
            dst.alpha_composite(src)
        else:
            dst.alpha_composite(src, dest=(max(0, dx), max(0, dy)), source=(max(0, -dx), max(0, -dy)))

    def render_realtime_frame(self, now: float) -> Image.Image:
        mx, my = get_global_cursor()
        head_scr_x = self.root.winfo_x() + 8 + self.hx + self.hw * 0.5
        head_scr_y = self.root.winfo_y() + 68 + self.hy + self.hh * 0.45
        nx = max(-1.0, min(1.0, (mx - head_scr_x) / 360.0))
        ny = max(-1.0, min(1.0, (my - head_scr_y) / 360.0))

        iris_dx = int(round(nx * 5.6 * self.pet_scale))
        iris_dy = int(round(ny * 3.4 * self.pet_scale))
        breath_idx = int((now / 3.14159) * self.IDLE_BREATH_FRAMES) % self.IDLE_BREATH_FRAMES

        canvas = Image.new("RGBA", (self.cw, self.ch), (0, 0, 0, 0))

        if now < self.sweep_until:
            prog = max(0.0, min(1.0, (now - self.sweep_start_t) / self.SWEEP_DUR))
            s_idx = int(round(prog * (self.SWEEP_FRAMES - 1)))
            canvas.alpha_composite(self.get_sweep_body_frame(s_idx))
        else:
            canvas.alpha_composite(self.get_idle_breath_frame(breath_idx))

        expr = self.current_expression if self.current_expression in EXPR_LABELS else "expr1"
        px = self.hx
        py = self.hy

        canvas.alpha_composite(self.expr_sclera[expr], dest=(px, py))
        if expr in OPEN_EYE_EXPRS:
            if self.is_blinking:
                canvas.alpha_composite(self.patch_closed_eyes, dest=(px, py))
            else:
                canvas.alpha_composite(self.expr_iris[expr], dest=(px + iris_dx, py + iris_dy))
                canvas.alpha_composite(self.expr_frame[expr], dest=(px, py))

        if now < self.miko_speak_until:
            mouth_step = int(now * 11.5) % 4
            if mouth_step == 2:
                canvas.alpha_composite(self.patch_mouth_open, dest=(px, py))
            elif mouth_step in (1, 3):
                canvas.alpha_composite(self.patch_mouth_half, dest=(px, py))
            else:
                canvas.alpha_composite(self.patch_mouth_closed, dest=(px, py))

        if now < self.fox_wag_until:
            fp = max(0.0, min(1.0, (now - self.fox_wag_start_t) / self.FOX_WAG_DUR))
            f_idx = int(round(fp * (self.FOX_WAG_FRAMES - 1)))
            canvas.alpha_composite(self.get_fox_wag_frame(f_idx))
        else:
            canvas.alpha_composite(self.lyr_fox_tail)
        canvas.alpha_composite(self.get_fox_breath_frame(breath_idx))

        if now < self.slap_mark_until:
            self.paste_offset(canvas, self.lyr_slap_mark, 0, 0)

        arr = np.array(canvas)
        alpha = arr[:, :, 3].astype(np.float32) / 255.0
        out = np.empty((self.ch, self.cw, 3), dtype=np.uint8)
        out[:, :] = self.TRANSPARENT_RGB
        fg = alpha > 0.22
        matte_rgb = np.array([28, 24, 32], dtype=np.float32)
        comp = arr[:, :, :3].astype(np.float32) * alpha[:, :, None] + matte_rgb * (1.0 - alpha[:, :, None])
        comp_u8 = np.clip(comp, 4, 255).astype(np.uint8)
        out[fg] = comp_u8[fg]
        return Image.fromarray(out)

    def poll_backend_expression(self):
        try:
            req = urllib.request.Request(BACKEND_URL + "/api/status", method="GET")
            with urllib.request.urlopen(req, timeout=0.6) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                cfg = data.get("config") or {}
                remote_expr = cfg.get("current_expression")
                if (
                    remote_expr in EXPR_LABELS
                    and remote_expr != self.current_expression
                    and self.expr_revert_t == 0.0
                    and len(self.chest_clicks) == 0
                    and self.power_countdown <= 0
                ):
                    self.current_expression = remote_expr
                if "builtin_voice_enabled" in cfg:
                    bv = bool(cfg["builtin_voice_enabled"])
                    self._ui_queue.put(lambda v=bv: self.builtin_voice_var.set(v))
                spk_until_ts = float(cfg.get("speak_until_ts") or 0.0)
                rem_sec = spk_until_ts - time.time()
                if rem_sec > 0.15:
                    self.miko_speak_until = max(self.miko_speak_until, time.perf_counter() + min(12.0, rem_sec))
                    last_rep = (cfg.get("last_reply") or "").strip()
                    last_rep = re.sub(
                        r"[\(（\[【<＜][^\)）\]】>＞]{0,12}?[\d０-９]+\s*(?:文字|字|chars?|characters?|words?)[^\)）\]】>＞]*[\)）\]】>＞]",
                        "",
                        last_rep,
                    ).strip()
                    if last_rep and (last_rep != self._last_synced_reply or abs(spk_until_ts - self._last_synced_spk_ts) > 0.05):
                        self._last_synced_reply = last_rep
                        self._last_synced_spk_ts = spk_until_ts
                        self._ui_queue.put(lambda r=last_rep: self.show_bubble(r, 7500, speak_mouth=True))
        except Exception:
            pass

    def animate(self):
        now = time.perf_counter()

        if self.chest_clicks:
            now_ts = time.time()
            self.chest_clicks = [ts for ts in self.chest_clicks if (now_ts - ts) < 7.5]

        for slot in self._drop_slots:
            hdrop = int(slot[0])
            if hdrop:
                slot[0] = 0
                self.handle_wm_dropfiles(hdrop)

        while not self._ui_queue.empty():
            try:
                cb = self._ui_queue.get_nowait()
                cb()
            except Exception:
                pass

        self._warm_one_frame_step()

        if self.expr_revert_t > 0.0 and now >= self.expr_revert_t:
            self.expr_revert_t = 0.0
            if self.current_expression != "expr1" and self.power_countdown <= 0 and len(self.chest_clicks) == 0:
                self.set_mvu_expression("expr1", announce=False)

        if now >= self.next_blink_t:
            if self.is_blinking:
                self.is_blinking = False
                self.next_blink_t = now + random.uniform(2.6, 5.2)
            else:
                self.is_blinking = True
                self.next_blink_t = now + 0.14

        if now - self.last_poll_t > 0.6:
            self.last_poll_t = now
            threading.Thread(target=self.poll_backend_expression, daemon=True).start()

        im = self.render_realtime_frame(now)
        self.tk_img = ImageTk.PhotoImage(im)
        self.canvas.itemconfig(self.img_item, image=self.tk_img)

        self.root.after(33, self.animate)

    def show_bubble(self, text: str, duration_ms: int = 5500, speak_mouth: bool = True):
        if self.bubble_hide_after:
            self.root.after_cancel(self.bubble_hide_after)
        self.bubble_lbl.config(text=text, wraplength=self.win_w - 12)
        self.bubble_lbl.place(x=6, y=2, width=self.win_w - 12)
        self.bubble_hide_after = self.root.after(duration_ms, self.hide_bubble)
        if speak_mouth and not text.startswith("(") and not text.startswith("🎭") and not text.startswith("🔊") and not text.startswith("🔇") and not text.startswith("✅"):
            spk_dur = min(4.2, max(1.6, len(text) * 0.07))
            self.miko_speak_until = max(self.miko_speak_until, time.perf_counter() + spk_dur)

    def hide_bubble(self):
        self.bubble_lbl.place_forget()
        self.bubble_hide_after = None

    def focus_chat_input(self, event=None):
        if not self.chat_visible:
            return
        try:
            self.root.update_idletasks()
            hi = self.root.winfo_id()
            ht = user32.GetParent(hi) or hi
            fg = user32.GetForegroundWindow()
            fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
            cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
            if fg_tid and fg_tid != cur_tid:
                user32.AttachThreadInput(fg_tid, cur_tid, True)
            user32.SetForegroundWindow(ht)
            user32.SetActiveWindow(ht)
            user32.SetFocus(hi)
            if fg_tid and fg_tid != cur_tid:
                user32.AttachThreadInput(fg_tid, cur_tid, False)
            self.root.focus_force()
            self.chat_entry.focus_set()
        except Exception:
            pass

    def toggle_chat_bar(self, force: bool = None):
        if force is not None:
            self.chat_visible = force
        else:
            self.chat_visible = not self.chat_visible
        if self.chat_visible:
            if hasattr(self, "chat_open_btn"):
                self.chat_open_btn.place_forget()
            self.chat_frame.place(x=6, y=self.win_h - 30, width=self.win_w - 12, height=28)
            self.chat_frame.lift()
            self.focus_chat_input()
            self.chat_entry.icursor("end")
            self.root.after(60, self.focus_chat_input)
        else:
            self.chat_frame.place_forget()
            if hasattr(self, "chat_open_btn"):
                self.chat_open_btn.place(x=self.win_w - 64, y=self.win_h - 26, width=58, height=22)

    def on_send_mini_chat(self, event=None):
        msg = self.chat_entry.get().strip()
        self.chat_entry.delete(0, "end")
        self.toggle_chat_bar(False)
        if not msg:
            return
        self.show_bubble("💬 Hidzuki is thinking...", 35000, speak_mouth=False)
        threading.Thread(target=self._send_chat_worker, args=(msg,), daemon=True).start()

    def _send_chat_worker(self, msg: str):
        try:
            body = json.dumps({"message": msg}).encode("utf-8")
            req = urllib.request.Request(
                BACKEND_URL + "/api/desktop_chat",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                if data.get("ok"):
                    reply = data.get("reply") or "..."
                    expr = data.get("expression") or "expr1"
                    self._ui_queue.put(lambda r=reply, ex=expr: self.apply_ai_mvu_reply(r, ex))
                    return
        except Exception:
            pass
        self._ui_queue.put(lambda: self.apply_ai_mvu_reply("I'm always right here in your bottom-right corner♪ (Right-click me to open the Web Control Panel!)", "expr1"))

    def apply_ai_mvu_reply(self, reply: str, expr: str):
        reply = re.sub(
            r"[\(（\[【<＜][^\)）\]】>＞]{0,12}?[\d０-９]+\s*(?:文字|字|chars?|characters?|words?)[^\)）\]】>＞]*[\)）\]】>＞]",
            "",
            reply or "",
        ).strip() or "..."
        self._last_synced_reply = reply
        self._last_synced_spk_ts = time.time() + 10.0
        if expr in EXPR_LABELS:
            self.current_expression = expr
        spk_dur = min(10.0, max(2.4, len(reply) * 0.08))
        self.miko_speak_until = max(self.miko_speak_until, time.perf_counter() + spk_dur)
        self.show_bubble(reply, 9000, speak_mouth=True)
        threading.Thread(target=self._speak_tts_worker, args=(reply, spk_dur), daemon=True).start()

    def _speak_tts_worker(self, text: str, min_speak_dur: float = 2.6):
        clean = re.sub(
            r"[\(（\[【<＜][^\)）\]】>＞]{0,12}?[\d０-９]+\s*(?:文字|字|chars?|characters?|words?)[^\)）\]】>＞]*[\)）\]】>＞]",
            "",
            text or "",
        ).strip()
        if not clean:
            return
        t0 = time.perf_counter()
        min_end_t = t0 + max(min_speak_dur, min(10.0, max(2.2, len(clean) * 0.08)))
        self.miko_speak_until = max(self.miko_speak_until, min_end_t)

        cfg = self.read_local_config()
        if not cfg.get("tts_enabled", True):
            return

        winmm = ctypes.windll.winmm
        audio_tmp = os.path.join(BASE_DIR, "_miko_tts_temp.mp3")
        wav_tmp = os.path.join(BASE_DIR, "_miko_tts_temp.wav")
        played = False

        ch = cfg.get("tts_channel", "cloud")

        # Channel C: Local VOICEVOX Engine (http://127.0.0.1:50021)
        if ch == "voicevox":
            vv_url = (cfg.get("voicevox_url") or "http://127.0.0.1:50021").rstrip("/")
            spk = int(cfg.get("voicevox_speaker", 10))
            try:
                q_url = f"{vv_url}/audio_query?text={urllib.parse.quote(clean)}&speaker={spk}"
                req_q = urllib.request.Request(q_url, data=b"", method="POST")
                with urllib.request.urlopen(req_q, timeout=8) as r_q:
                    q_json = r_q.read()
                req_s = urllib.request.Request(
                    f"{vv_url}/synthesis?speaker={spk}",
                    data=q_json,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req_s, timeout=15) as r_s:
                    raw_wav = r_s.read()
                if len(raw_wav) > 256:
                    with open(wav_tmp, "wb") as f:
                        f.write(raw_wav)
                    self.miko_speak_until = time.perf_counter() + 25.0
                    winsound.PlaySound(wav_tmp, winsound.SND_FILENAME)
                    self.miko_speak_until = 0.0
                    played = True
            except Exception:
                pass

        # Channel B: Local Voice Clone (GPT-SoVITS / CosyVoice on 127.0.0.1:9880)
        if not played and ch == "local":
            local_url = (cfg.get("local_tts_url") or "http://127.0.0.1:9880").rstrip("/")
            try:
                params = {
                    "text": clean,
                    "text_language": cfg.get("local_ref_lang", "en"),
                    "ref_audio_path": cfg.get("local_ref_wav", ""),
                    "prompt_text": cfg.get("local_ref_text", ""),
                    "prompt_language": cfg.get("local_ref_lang", "en"),
                }
                q = urllib.parse.urlencode(params)
                with urllib.request.urlopen(f"{local_url}/?{q}", timeout=12) as resp:
                    raw_audio = resp.read()
                if len(raw_audio) > 256:
                    with open(wav_tmp, "wb") as f:
                        f.write(raw_audio)
                    self.miko_speak_until = time.perf_counter() + 25.0
                    winsound.PlaySound(wav_tmp, winsound.SND_FILENAME)
                    self.miko_speak_until = 0.0
                    played = True
            except Exception:
                pass

        # Channel A: Cloud OpenAI-Compatible TTS (/v1/audio/speech)
        if not played and ch == "cloud":
            tts_url = (cfg.get("cloud_tts_url") or "").strip()
            tts_key = (cfg.get("cloud_tts_key") or cfg.get("api_key") or "").strip()
            if tts_url and tts_key:
                try:
                    req_body = json.dumps({
                        "model": cfg.get("cloud_tts_model") or "tts-1",
                        "input": clean,
                        "voice": cfg.get("cloud_tts_voice") or "nova",
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        tts_url,
                        data=req_body,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {tts_key}",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        raw_mp3 = resp.read()
                    if len(raw_mp3) > 256:
                        with open(audio_tmp, "wb") as f:
                            f.write(raw_mp3)
                        winmm.mciSendStringW("close miko_tts", None, 0, 0)
                        winmm.mciSendStringW(f'open "{audio_tmp}" type mpegvideo alias miko_tts', None, 0, 0)
                        self.miko_speak_until = time.perf_counter() + 25.0
                        winmm.mciSendStringW("play miko_tts wait", None, 0, 0)
                        winmm.mciSendStringW("close miko_tts", None, 0, 0)
                        self.miko_speak_until = 0.0
                        played = True
                except Exception:
                    pass

        # Channel D / Zero-Config Fallback: Native Windows SAPI Voice
        if not played:
            try:
                safe_txt = clean.replace("'", " ").replace('"', " ").replace("\r", " ").replace("\n", " ")
                ps_cmd = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$s.Rate = 1; "
                    f"$s.Speak('{safe_txt}')"
                )
                sapi_t0 = time.perf_counter()
                self.miko_speak_until = max(self.miko_speak_until, min_end_t)
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    creationflags=0x08000000,
                    timeout=20,
                )
                if time.perf_counter() - sapi_t0 > 1.2:
                    self.miko_speak_until = 0.0
                else:
                    self.miko_speak_until = max(self.miko_speak_until, min_end_t)
            except Exception:
                self.miko_speak_until = max(self.miko_speak_until, min_end_t)

    def _post_backend_async(self, path: str, payload: dict, timeout: float = 2.0):
        def _worker():
            try:
                req = urllib.request.Request(
                    BACKEND_URL + path,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout):
                    pass
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def set_mvu_expression(self, expr_id: str, announce: bool = False):
        if expr_id not in EXPR_LABELS:
            return
        self.current_expression = expr_id
        self._post_backend_async("/api/set_expression", {"expression": expr_id}, timeout=1.5)
        if announce:
            self.show_bubble(f"🎭 Expression: {EXPR_LABELS[expr_id]}", 4000)

    def on_mouse_down(self, event):
        self.drag_start_x = event.x_root - self.root.winfo_x()
        self.drag_start_y = event.y_root - self.root.winfo_y()
        self.press_x_root = event.x_root
        self.press_y_root = event.y_root
        self.drag_moved = False

    def on_mouse_drag(self, event):
        if abs(event.x_root - self.press_x_root) > 10 or abs(event.y_root - self.press_y_root) > 10:
            self.drag_moved = True
        if self.drag_moved:
            nx = event.x_root - self.drag_start_x
            ny = event.y_root - self.drag_start_y
            self.root.geometry(f"+{nx}+{ny}")

    def on_mouse_up(self, event):
        if self.drag_moved:
            return
        orig_x = (event.x - 8) / self.pet_scale + self.CROP_X0
        orig_y = (event.y - 68) / self.pet_scale + self.CROP_Y0

        now_ts = time.time()
        self.chest_clicks = [ts for ts in self.chest_clicks if (now_ts - ts) < 7.5]

        # If a chest-click combo (1..4) is already in progress, any click on her upper/mid torso continues the 5-click combo!
        if len(self.chest_clicks) >= 1 and (375 <= orig_x <= 615 and 160 <= orig_y <= 500):
            self.handle_chest_click()
            return

        # 1. Little White Fox & Tail Hotspot (x=600..902, y=610..1018) -> Wag Tail 2x & Launch Bound App!
        if 600 <= orig_x <= 902 and 610 <= orig_y <= 1018:
            self.handle_fox_tail_click()
        # 2. Shrine Maiden Chest Hotspot (x=400..600, y=185..415) -> 5-Click Slap & 20s Shutdown Easter Egg!
        elif 400 <= orig_x <= 600 and 185 <= orig_y <= 415:
            self.handle_chest_click()
        # 3. Bamboo Broom Hotspot (x=170..465, y=420..1015) -> Sweep 2x + Bamboo Broom Sound!
        elif 170 <= orig_x <= 465 and 420 <= orig_y <= 1015:
            self.trigger_broom_demo()
        # 4. Head Hotspot (orig_y < 185) -> Head Pat (`② Beaming Smile`)
        elif orig_y < 185:
            self.expr_revert_t = time.perf_counter() + 2.6
            self.set_mvu_expression("expr2", announce=False)
            self.show_bubble("😊 Ehehe, thank you for the head pat♪")

    def on_right_click(self, event):
        self.autostart_var.set(is_autostart_enabled())
        cfg = self.read_local_config()
        self.builtin_voice_var.set(cfg.get("builtin_voice_enabled", True))
        self.menu.tk_popup(event.x_root, event.y_root)

    def toggle_builtin_voice(self):
        val = bool(self.builtin_voice_var.get())
        self._post_backend_async("/api/save_config", {"builtin_voice_enabled": val}, timeout=1.5)
        if val:
            self.show_bubble("🔊 Built-in Bonus Voice turned ON")
        else:
            self.show_bubble("🔇 Built-in Bonus Voice turned OFF")

    def trigger_broom_demo(self):
        self.sweep_start_t = time.perf_counter()
        self.sweep_until = self.sweep_start_t + self.SWEEP_DUR
        self.expr_revert_t = self.sweep_until + 0.55
        self.set_mvu_expression("expr3", announce=False)
        if os.path.exists(self.wav_sweep_2x):
            winsound.PlaySound(self.wav_sweep_2x, winsound.SND_FILENAME | winsound.SND_ASYNC)
        self.show_bubble("🧹 (Swish, swish...!) All swept clean and tidy for you♪ ✨", 4200)

    def handle_fox_tail_click(self):
        self.fox_wag_start_t = time.perf_counter()
        self.fox_wag_until = self.fox_wag_start_t + self.FOX_WAG_DUR
        self.expr_revert_t = self.fox_wag_until + 0.8
        self.set_mvu_expression("expr4", announce=False)
        cfg = self.read_local_config()
        bound_path = (cfg.get("bound_app_path") or "").strip()
        if bound_path:
            bname = cfg.get("bound_app_name") or os.path.splitext(os.path.basename(bound_path))[0] or bound_path
            self.show_bubble(f'🦊 Launching "{bname}" for you♪ 💕', 4500)
            self._post_backend_async("/api/launch_bound_app", {"bound_app_path": bound_path}, timeout=3.0)
        else:
            self.show_bubble("🦊 Pick an app to bind to Little White Fox's tail 💕", 5000)
            self.bind_fox_tail_app(launch_after=True)

    def bind_fox_tail_app(self, launch_after: bool = False):
        def _worker():
            try:
                req = urllib.request.Request(BACKEND_URL + "/api/browse_app", data=b"{}", method="POST")
                with urllib.request.urlopen(req, timeout=125) as resp:
                    d = json.loads(resp.read().decode("utf-8", errors="replace"))
                    if d.get("ok") and d.get("path"):
                        name = d.get("name") or os.path.basename(d["path"])
                        self._ui_queue.put(lambda n=name: self.show_bubble(f'🦊 Bound "{n}" to the fox\'s tail! Click its tail anytime to launch it 💕', 6500))
                        if launch_after:
                            urllib.request.urlopen(
                                urllib.request.Request(
                                    BACKEND_URL + "/api/launch_bound_app",
                                    data=json.dumps({"bound_app_path": d["path"]}).encode("utf-8"),
                                    headers={"Content-Type": "application/json"},
                                ),
                                timeout=3.0,
                            )
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def handle_chest_click(self):
        now = time.time()
        self.chest_clicks = [ts for ts in self.chest_clicks if (now - ts) < 7.5]
        self.chest_clicks.append(now)
        cnt = len(self.chest_clicks)
        self.expr_revert_t = time.perf_counter() + 7.5

        if cnt == 1:
            self.set_mvu_expression("expr5", announce=False)
            self.show_bubble("😳 (Shy Blush 1/5) ...Eh?! Y-You mustn't touch me there...!")
        elif cnt == 2:
            self.set_mvu_expression("expr6", announce=False)
            self.show_bubble("😣 (Bashful 2/5 >_<) Kyaa...! Stop teasing me or I'll really get angry!")
        elif cnt == 3:
            self.set_mvu_expression("expr7", announce=False)
            self.show_bubble("💢 (Pouting 3/5) Hmph! That's 3 warnings already!")
        elif cnt == 4:
            self.set_mvu_expression("expr8", announce=False)
            self.show_bubble("🥺 (Teary Eyes 4/5) Uuu... poke me 1 more time and divine punishment will truly strike...!")
        elif cnt >= 5:
            self.chest_clicks.clear()
            self.expr_revert_t = 0.0
            self.trigger_power_penalty()

    def trigger_power_penalty(self):
        if self.power_timer_id:
            try:
                self.root.after_cancel(self.power_timer_id)
            except Exception:
                pass
            self.power_timer_id = None
        self.set_mvu_expression("expr9", announce=False)
        self.slap_mark_until = time.perf_counter() + 4.5

        cfg = self.read_local_config()
        if cfg.get("builtin_voice_enabled", True) and os.path.exists(self.wav_kya_combo):
            winsound.PlaySound(self.wav_kya_combo, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif os.path.exists(self.wav_slap_only):
            winsound.PlaySound(self.wav_slap_only, winsound.SND_FILENAME | winsound.SND_ASYNC)

        mode = random.choice(["shutdown", "restart"])
        flag = "/s" if mode == "shutdown" else "/r"
        label = "Shutdown" if mode == "shutdown" else "Restart"
        self.power_countdown = 20
        subprocess.run(
            ["shutdown", flag, "/t", str(self.power_countdown), "/c", f"Shrine Maiden's Divine Punishment: System {label} in 20s! Click the green [I'm sorry!!] button to abort!"],
            creationflags=0x08000000,
        )
        self.show_bubble(f'⚡ "Kyaa...! Pervert!" (SLAP!) System [{label}] in 20s! Click the green button below to apologize!', 22000)
        self.mercy_btn.config(text=f"🛑 I'm sorry!! (Abort {label} {self.power_countdown}s)")
        self.mercy_btn.place(x=6, y=42, width=self.win_w - 12, height=26)
        self.mercy_btn.lift()
        self.tick_power_countdown(label)

    def tick_power_countdown(self, label):
        if self.power_countdown <= 0:
            return
        self.mercy_btn.config(text=f"🛑 I'm sorry!! (Abort {label} {self.power_countdown}s)")
        self.power_countdown -= 1
        self.power_timer_id = self.root.after(1000, lambda: self.tick_power_countdown(label))

    def cancel_power_penalty(self):
        if self.power_timer_id:
            self.root.after_cancel(self.power_timer_id)
            self.power_timer_id = None
        self.power_countdown = 0
        self.slap_mark_until = 0.0
        subprocess.run(["shutdown", "/a"], creationflags=0x08000000)
        self.mercy_btn.place_forget()
        self.expr_revert_t = time.perf_counter() + 3.0
        self.set_mvu_expression("expr7", announce=False)
        self.show_bubble("Hmph... I'll forgive you this time! Shutdown aborted—no more naughty poking!")

    def toggle_autostart(self):
        enabled = self.autostart_var.get()
        set_autostart(enabled)
        self.show_bubble("✅ Windows Startup Auto-Run turned ON" if enabled else "Windows Startup Auto-Run turned OFF")

    def snap_to_bottom_right(self):
        scr_w = self.root.winfo_screenwidth()
        scr_h = self.root.winfo_screenheight()
        self.root.geometry(f"+{scr_w - self.win_w - 18}+{scr_h - self.win_h - 46}")

    def open_backend_web(self):
        webbrowser.open(BACKEND_URL + "/pet")

    def quit_app(self):
        self.root.destroy()
        os._exit(0)


if __name__ == "__main__":
    bg_thread = threading.Thread(target=start_backend_thread, daemon=True)
    bg_thread.start()

    root = tk.Tk()
    app = MikoFoxDesktopPetApp(root)
    root.mainloop()
