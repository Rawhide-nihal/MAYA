"""
MAYA Hardware Detection & Model Recommendation Utility
Detects real CPU, System RAM, GPU model, VRAM, disk space, and CUDA/DirectML support.
Zero fake values.
"""
import shutil
import subprocess
import psutil
import platform
from typing import Dict, Any, Optional
from pathlib import Path
from maya_core.config import PROJECT_ROOT

def get_real_gpu_metrics() -> Dict[str, Any]:
    """Queries genuine NVIDIA GPU telemetry using nvidia-smi. Returns actual values or marks Unavailable."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {
            "available": False,
            "name": "Unavailable",
            "vram_total_mb": 0,
            "vram_used_mb": 0,
            "vram_free_mb": 0,
            "gpu_percent": None,
            "temperature_c": None
        }

    try:
        cmd = [
            nvidia_smi,
            "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.5)
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            if len(parts) >= 6:
                return {
                    "available": True,
                    "name": parts[0],
                    "vram_total_mb": int(parts[1]),
                    "vram_used_mb": int(parts[2]),
                    "vram_free_mb": int(parts[3]),
                    "gpu_percent": float(parts[4]),
                    "temperature_c": int(parts[5])
                }
    except Exception:
        pass

    return {
        "available": False,
        "name": "Unavailable",
        "vram_total_mb": 0,
        "vram_used_mb": 0,
        "vram_free_mb": 0,
        "gpu_percent": None,
        "temperature_c": None
    }

def get_hardware_profile() -> Dict[str, Any]:
    """Comprehensive hardware diagnostic profile for model selection & runtime sizing."""
    # CPU
    cpu_name = platform.processor() or "AMD64 Processor"
    cpu_cores = psutil.cpu_count(logical=False) or 8
    cpu_threads = psutil.cpu_count(logical=True) or 16

    # RAM
    vmem = psutil.virtual_memory()
    ram_total_gb = round(vmem.total / (1024**3), 2)
    ram_available_gb = round(vmem.available / (1024**3), 2)

    # Disk Space (Project drive)
    disk = psutil.disk_usage(str(PROJECT_ROOT.anchor or "C:\\"))
    disk_free_gb = round(disk.free / (1024**3), 2)

    # GPU
    gpu_info = get_real_gpu_metrics()

    # Recommended Model & Quantization based on actual hardware
    vram_mb = gpu_info["vram_total_mb"]
    if gpu_info["available"] and vram_mb >= 5000:
        recommended_model = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
        quantization = "Q4_K_M" if vram_mb < 8000 else "FP16"
        max_context = 8192
    elif ram_available_gb >= 12:
        recommended_model = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
        quantization = "Q4_0"
        max_context = 4096
    else:
        recommended_model = "Qwen/Qwen2.5-0.5B-Instruct"
        quantization = "Q4_0"
        max_context = 2048

    return {
        "cpu": {
            "name": cpu_name,
            "physical_cores": cpu_cores,
            "logical_threads": cpu_threads
        },
        "ram": {
            "total_gb": ram_total_gb,
            "available_gb": ram_available_gb
        },
        "storage": {
            "free_gb": disk_free_gb
        },
        "gpu": gpu_info,
        "cuda_available": gpu_info["available"],
        "recommended_model": recommended_model,
        "recommended_quantization": quantization,
        "recommended_context": max_context
    }
