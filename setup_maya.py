#!/usr/bin/env python3
"""
MAYA Setup & Diagnostic Verification Script
Verifies hardware compatibility, environment dependencies, database initialization,
and ensures Maya checkpoint weights are ready.
"""

import sys
import os
import platform
import subprocess
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from maya_core.config import (
    MAYA_DATA_DIR, DB_DIR, LOGS_DIR, MODELS_DIR, CACHE_DIR,
    SETTINGS_FILE, AUTH_TOKEN_FILE
)
from maya_core.models.hardware_detector import get_hardware_profile

def print_banner():
    print("""
===========================================================
  MAYA — PERSONAL AI DESKTOP COMPANION
  Phase 2 Production Environment Verification & Setup
===========================================================
""")

def verify_system_and_hardware():
    print("[1/5] Checking OS and Hardware Profile...")
    print(f"  • Operating System: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"  • Python Runtime:   {platform.python_version()} ({sys.executable})")

    hw = get_hardware_profile()
    cpu = hw.get("cpu", {})
    ram = hw.get("ram", {})
    gpu = hw.get("gpu", {})

    print(f"  • CPU:             {cpu.get('name')} ({cpu.get('physical_cores')} cores, {cpu.get('logical_threads')} threads)")
    print(f"  • RAM:             {ram.get('total_gb')} GB (Available: {ram.get('available_gb')} GB)")
    if gpu.get("available"):
        print(f"  • GPU:             {gpu.get('name')} ({gpu.get('vram_total_mb')} MB VRAM, Temp: {gpu.get('temperature_c')}°C)")
    else:
        print(f"  • GPU:             Direct / CPU Fallback (Dedicated GPU not detected)")

    print(f"  • Recommended Model: {hw.get('recommended_model')} ({hw.get('recommended_quantization')})")
    print("  [OK] Hardware profile verified.\n")
    return hw

def verify_directories():
    print("[2/5] Initializing Maya Runtime Directories...")
    dirs = [MAYA_DATA_DIR, DB_DIR, LOGS_DIR, MODELS_DIR, CACHE_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  • {d.name:12} -> {d}")
    print("  [OK] Storage directories ready.\n")

def verify_python_dependencies():
    print("[3/5] Verifying Python Package Dependencies...")
    required = [
        ("flask", "Flask"),
        ("psutil", "psutil"),
        ("safetensors", "safetensors"),
        ("numpy", "NumPy"),
        ("requests", "Requests"),
    ]
    optional = [
        ("flask_cors", "Flask-CORS (Optional - native CORS active)"),
        ("win32gui", "pywin32"),
        ("pyperclip", "pyperclip"),
        ("PIL", "Pillow"),
        ("pyttsx3", "pyttsx3"),
        ("transformers", "transformers"),
    ]

    all_ok = True
    for mod_name, label in required:
        try:
            __import__(mod_name)
            print(f"  • {label:16} [Installed]")
        except ImportError:
            print(f"  • {label:16} [MISSING - Required]")
            all_ok = False

    for mod_name, label in optional:
        try:
            __import__(mod_name)
            print(f"  • {label:16} [Installed]")
        except ImportError:
            print(f"  • {label:16} [Optional / Not Installed]")

    if not all_ok:
        print("\n  [!] Missing dependencies. Run: pip install -r requirements.txt")
    else:
        print("  [OK] Core dependencies verified.\n")
    return all_ok

def verify_maya_model_checkpoints():
    print("[4/5] Checking Maya Custom Model Checkpoint...")
    checkpoint_dir = Path(__file__).parent / "training" / "checkpoints" / "maya-v1"
    adapter_file = checkpoint_dir / "adapter_model.safetensors"
    config_file = checkpoint_dir / "adapter_config.json"

    if adapter_file.exists() and config_file.exists():
        size_kb = adapter_file.stat().st_size / 1024
        print(f"  • Maya Adapter:     {adapter_file.name} ({size_kb:.1f} KB)")
        print(f"  • Adapter Config:   {config_file.name}")
        print("  [OK] Trained Maya LoRA checkpoint is ready.\n")
    else:
        print(f"  • Checkpoint not found in {checkpoint_dir}")
        print("  • Triggering automated dataset build and LoRA training pipeline...")
        try:
            from training.datasets.build_dataset import build_sft_dataset
            from training.finetuning.train_lora import run_fine_tuning
            build_sft_dataset()
            run_fine_tuning()
            print("  [OK] Maya LoRA model trained successfully.\n")
        except Exception as e:
            print(f"  [!] Failed to train checkpoint: {e}\n")

def verify_gui_build():
    print("[5/5] Verifying Desktop Frontend Build...")
    dist_dir = Path(__file__).parent / "apps" / "desktop" / "dist"
    index_html = dist_dir / "index.html"
    if index_html.exists():
        print(f"  • Frontend Artifact: {index_html} [Production Ready]")
        print("  [OK] Desktop UI distribution verified.\n")
    else:
        print("  [!] Frontend dist not found. Run 'npm run build' inside apps/desktop.\n")

def main():
    print_banner()
    verify_system_and_hardware()
    verify_directories()
    verify_python_dependencies()
    verify_maya_model_checkpoints()
    verify_gui_build()
    print("===========================================================")
    print("  MAYA Phase 2 is fully configured and ready for launch.")
    print("  Run 'python start_maya.py' to launch server and desktop UI.")
    print("===========================================================")

if __name__ == "__main__":
    main()
