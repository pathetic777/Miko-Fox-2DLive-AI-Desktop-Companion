# -*- coding: utf-8 -*-
"""
Packages the Shrine Maiden & Little White Fox 2D Live Desktop Companion (English Edition) into:
1. Standalone executable folder (`dist/MikoFoxPet/MikoFoxPet.exe`) via PyInstaller
2. Portable ZIP archive:
   - `D:\bilibili_animation_study\Hidzuki_Miko_Fox_2DLive_Desktop_Companion_EN_Portable.zip`
3. One-Click GUI Setup Installer EXE:
   - `D:\bilibili_animation_study\Hidzuki_Miko_Fox_2DLive_Desktop_Companion_EN_Setup.exe`
"""
import os
import sys
import json
import shutil
import zipfile
import subprocess

ROOT_DIR = r"D:\bilibili_animation_study"
WORK_DIR = os.path.join(ROOT_DIR, "miko_fox_2dlive_en")
BUILD_WS = os.path.join(WORK_DIR, "release_build")
os.makedirs(BUILD_WS, exist_ok=True)

PYINSTALLER_EXE = os.path.join(ROOT_DIR, "see-through", "venv", "Scripts", "pyinstaller.exe")

ASSETS_DIR = os.path.join(WORK_DIR, "miko_pet_assets")
ico_path = os.path.join(ASSETS_DIR, "miko_pet.ico")
pet_main_py = os.path.join(WORK_DIR, "miko_desktop_pet_app.py")
backend_py = os.path.join(WORK_DIR, "miko_pet_backend_server.py")
web_html = os.path.join(WORK_DIR, "Web_Control_Center.html")

exclude_mods = [
    "torch", "torchvision", "torchaudio", "scipy", "matplotlib", "pandas",
    "cv2", "timm", "transformers", "diffusers", "accelerate", "onnxruntime",
    "sklearn", "sympy", "pytest", "IPython", "notebook", "jedi", "pygments",
    "huggingface_hub", "safetensors", "tqdm", "psutil", "pyarrow",
]

pyi_cmd = [
    PYINSTALLER_EXE,
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "MikoFoxPet",
    "--icon", ico_path,
    "--paths", WORK_DIR,
    "--hidden-import", "miko_pet_backend_server",
    "--hidden-import", "winsound",
    "--hidden-import", "urllib.parse",
    "--hidden-import", "urllib.request",
    "--hidden-import", "urllib.error",
    "--hidden-import", "http.server",
]
for mod in exclude_mods:
    pyi_cmd.extend(["--exclude-module", mod])
pyi_cmd.append(pet_main_py)

print("[1/4] Freezing MikoFoxPet.exe (English Edition) via PyInstaller...")
subprocess.run(pyi_cmd, cwd=BUILD_WS, check=True)

dist_dir = os.path.join(BUILD_WS, "dist", "MikoFoxPet")
assert os.path.exists(os.path.join(dist_dir, "MikoFoxPet.exe")), "MikoFoxPet.exe was not created!"

print("[2/4] Copying portable assets, English 3-Box Web Control Center & default config...")
dst_assets = os.path.join(dist_dir, "miko_pet_assets")
if os.path.exists(dst_assets):
    shutil.rmtree(dst_assets)
shutil.copytree(ASSETS_DIR, dst_assets)

shutil.copy2(web_html, os.path.join(dist_dir, "Web_Control_Center.html"))
shutil.copy2(backend_py, os.path.join(dist_dir, "miko_pet_backend_server.py"))
shutil.copy2(ico_path, os.path.join(dist_dir, "miko_pet.ico"))

sys.path.insert(0, WORK_DIR)
from miko_pet_backend_server import DEFAULT_CONFIG
clean_cfg = dict(DEFAULT_CONFIG)
clean_cfg["api_key"] = ""
clean_cfg["cloud_tts_key"] = ""
clean_cfg["bound_app_path"] = ""
clean_cfg["bound_app_name"] = ""
with open(os.path.join(dist_dir, "pet_config.json"), "w", encoding="utf-8") as f:
    json.dump(clean_cfg, f, ensure_ascii=False, indent=2)

bat_content = (
    "@echo off\r\n"
    "cd /d \"%~dp0\"\r\n"
    "start \"\" \"%~dp0MikoFoxPet.exe\"\r\n"
)
with open(os.path.join(dist_dir, "Launch_Hidzuki_Miko_Fox.bat"), "w", encoding="utf-8") as f:
    f.write(bat_content)

readme_txt = """Shrine Maiden & Little White Fox (Hidzuki) — 2D Live AI Desktop Companion (English Edition)
===========================================================================================
⭐ GitHub Repository: https://github.com/pathetic777/Miko-Fox-2DLive-AI-Desktop-Companion
   (If you enjoy Hidzuki, please give us a ⭐ Star & Upvote on GitHub!)

■ How to Launch
Double-click "MikoFoxPet.exe" (or "Launch_Hidzuki_Miko_Fox.bat"). Hidzuki and Little White Fox will appear in the bottom-right corner of your Windows desktop!

■ Physical Desktop Interactions & Features
• Drag & drop any unwanted file onto her bamboo broom -> She sweeps it twice into the Windows Recycle Bin!
• Click Little White Fox's fluffy tail -> Wags its tail twice and launches your bound app or website!
• Click the "💬 Talk" button at her feet (or right-click her) -> Opens the mini chat bar or the 3-Box Web Control Panel (http://127.0.0.1:18766/pet).
• Right-click her -> Switch between all 9 expressions, resize (Small / Standard / Large), or enable Windows Startup Auto-Run.
• Poke her chest 5 times in a row -> Triggers the Divine Slap & 20s Shutdown Easter Egg!
  (Click the green "🛑 I'm sorry!! (Abort Shutdown)" button to cancel immediately.)

■ Free AI Brain Setup (Optional)
• Free Cloud API (Recommended for any PC): Get a 100% free Google Gemini API key from Google AI Studio (https://aistudio.google.com/app/apikey), open the Web Control Panel, click "✨ Preset: Free Google Gemini", paste your key, and click Save!
• Free Local LLM (For PCs with a dedicated GPU): Install Ollama (https://ollama.com/), run `ollama run qwen2.5:7b` or `ollama run gemma3`, and click "💻 Preset: Local Ollama" in the Web Control Panel!

■ Credits & Contact
• Built-in Bonus Voice ("Kyaa...! Ecchi!" 1 line only): VOICEVOX:Amahare Hau (can be toggled ON/OFF anytime).
• Custom 2D Live / AI Desktop Companion Commissions: wm2841944156@gmail.com
"""
with open(os.path.join(dist_dir, "README_How_To_Use.txt"), "w", encoding="utf-8") as f:
    f.write(readme_txt)

print("[3/4] Creating Portable ZIP archives...")
payload_zip = os.path.join(BUILD_WS, "payload.zip")
zip_work = os.path.join(WORK_DIR, "Hidzuki_Miko_Fox_2DLive_Desktop_Companion_EN_Portable.zip")
zip_root = os.path.join(ROOT_DIR, "Hidzuki_Miko_Fox_2DLive_Desktop_Companion_EN_Portable.zip")

with zipfile.ZipFile(payload_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for root, dirs, files in os.walk(dist_dir):
        for file in files:
            full_p = os.path.join(root, file)
            rel_p = os.path.relpath(full_p, dist_dir)
            zf.write(full_p, rel_p)

shutil.copy2(payload_zip, zip_work)
shutil.copy2(payload_zip, zip_root)

print("[4/4] Compiling Single-File Windows GUI Setup Installer EXE (English Edition)...")
setup_root = os.path.join(ROOT_DIR, "Hidzuki_Miko_Fox_2DLive_Desktop_Companion_EN_Setup.exe")
subprocess.run([sys.executable, os.path.join(WORK_DIR, "rebuild_installer_only.py")], cwd=WORK_DIR, check=True)

setup_mb = os.path.getsize(setup_root) / (1024 * 1024)
zip_mb = os.path.getsize(zip_root) / (1024 * 1024)
print(f"DONE! English Setup EXE: {setup_root} ({setup_mb:.2f} MB)")
print(f"DONE! English Portable ZIP: {zip_root} ({zip_mb:.2f} MB)")
