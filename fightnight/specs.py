"""Machine specs for the fight card. Stdlib plus one shell call per OS, nothing to install."""

from __future__ import annotations

import platform
import shutil
import subprocess


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _mac() -> dict:
    chip = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    mem = _run(["sysctl", "-n", "hw.memsize"])
    ram_gb = round(int(mem) / 2**30) if mem.isdigit() else None
    gpu = chip if "Apple" in chip else _run(["system_profiler", "SPDisplaysDataType"]).split("Chipset Model:")[-1].split("\n")[0].strip()
    return {"cpu": chip, "ram_gb": ram_gb, "gpu": gpu, "gpu_note": "unified memory" if "Apple" in chip else ""}


def _linux() -> dict:
    cpu = ""
    try:
        for line in open("/proc/cpuinfo"):
            if line.lower().startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    ram_gb = None
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemTotal"):
                ram_gb = round(int(line.split()[1]) / 2**20)
                break
    except OSError:
        pass
    return {"cpu": cpu, "ram_gb": ram_gb, **_nvidia()}


def _windows() -> dict:
    cpu = platform.processor()
    mem = _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
    ram_gb = round(int(mem) / 2**30) if mem.isdigit() else None
    return {"cpu": cpu, "ram_gb": ram_gb, **_nvidia()}


def _nvidia() -> dict:
    if not shutil.which("nvidia-smi"):
        return {"gpu": "none detected", "gpu_note": ""}
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    if not out:
        return {"gpu": "none detected", "gpu_note": ""}
    name, _, mem = out.split("\n")[0].partition(",")
    return {"gpu": name.strip(), "gpu_note": mem.strip()}


def collect() -> dict:
    system = platform.system()
    base = {"os": f"{system} {platform.release()}", "arch": platform.machine(), "python": platform.python_version()}
    if system == "Darwin":
        base["os"] = f"macOS {platform.mac_ver()[0]}"
        base.update(_mac())
    elif system == "Linux":
        base.update(_linux())
    elif system == "Windows":
        base.update(_windows())
    else:
        base.update({"cpu": platform.processor(), "ram_gb": None, "gpu": "unknown", "gpu_note": ""})
    return base
