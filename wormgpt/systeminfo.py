"""Hardware detection and recommended settings.

Reads total RAM (Windows API via ctypes), CPU core count, free disk and GPU
presence, then derives sane defaults for the active machine: best model tier
per family, CPU thread count and context window. Everything is stdlib-only.
"""

import ctypes
import os
import shutil
import sys
import time

from . import config as C
from . import models as M


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def total_ram_gb():
    """Total physical RAM in GB, or None when undetectable."""
    try:
        if sys.platform == "win32":

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            m = MEMORYSTATUSEX()
            m.dwLength = ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return m.ullTotalPhys / (1024 ** 3)
        elif sys.platform.startswith("linux"):
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) / (1024 * 1024)
    except Exception:
        pass
    return None


def cpu_count():
    return os.cpu_count() or 4


def free_disk_gb():
    try:
        return shutil.disk_usage(C.models_dir()).free / (1024 ** 3)
    except OSError:
        return 0.0


def _find_nvidia_smi():
    """nvidia-smi on PATH, or at its usual install locations."""
    try:
        exe = shutil.which("nvidia-smi")
        if exe:
            return exe
    except Exception:
        pass
    if sys.platform == "win32":
        for p in (r"C:\Windows\System32\nvidia-smi.exe",
                  r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
            try:
                if os.path.isfile(p):
                    return p
            except OSError:
                pass
    return ""


#: cache du sondage générique (PowerShell coûte ~1 s : on ne le fait pas à
#: chaque rafraîchissement du tableau de bord)
_GPU_PROBE = {"t": 0.0, "info": None, "done": False}


def _registry_vram_mb():
    """VRAM réelle lue dans le registre (contourne le plafond 32 bits).

    ``Win32_VideoController.AdapterRAM`` est un entier 32 bits : au-delà de
    4 Go il déborde et renvoie toujours ~4095 Mo. La valeur
    ``HardwareInformation.qwMemorySize`` du registre, elle, est un QWORD et
    donne la taille réelle (12 Go pour une RX 7700 XT par exemple).
    """
    if sys.platform != "win32":
        return 0.0
    try:
        import winreg
    except ImportError:
        return 0.0
    base = (r"SYSTEM\CurrentControlSet\Control\Class"
            r"\{4d36e968-e325-11ce-bfc1-08002be10318}")
    best = 0
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                if not sub.isdigit():
                    continue
                try:
                    with winreg.OpenKey(k, sub) as sk:
                        val, _ = winreg.QueryValueEx(
                            sk, "HardwareInformation.qwMemorySize")
                        best = max(best, int(val))
                except OSError:
                    continue
    except OSError:
        return 0.0
    return best / (1024 * 1024) if best > 0 else 0.0


def _generic_gpu(max_age=60.0):
    """Nom + VRAM de la première carte détectée (AMD/Intel/NVIDIA).

    Passe par Win32_VideoController : c'est la seule méthode sans dépendance
    qui voit TOUTES les cartes, y compris quand nvidia-smi est absent.
    """
    if sys.platform != "win32":
        return None
    if _GPU_PROBE["done"] and (time.time() - _GPU_PROBE["t"]) < max_age:
        return _GPU_PROBE["info"]
    info = None
    try:
        import json as _json
        import subprocess
        ps = ("Get-CimInstance Win32_VideoController | "
              "Where-Object { $_.Name } | "
              "Select-Object -First 4 Name, AdapterRAM, DriverVersion | "
              "ConvertTo-Json -Compress")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=12)
        raw = (out.stdout or "").strip()
        if raw:
            data = _json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            best = None
            for card in data or []:
                name = (card.get("Name") or "").strip()
                if not name or "Microsoft Basic" in name:
                    continue
                vram = card.get("AdapterRAM") or 0
                try:
                    vram = float(vram)
                except (TypeError, ValueError):
                    vram = 0.0
                # AdapterRAM est un champ 32 bits : > 4 Go il déborde. On lit
                # alors la vraie taille dans le registre.
                vram_mb = min(vram / (1024 * 1024), 4095.0) if vram > 0 else 0.0
                approx = vram_mb >= 4095.0
                if approx:
                    real = _registry_vram_mb()
                    if real > vram_mb:
                        vram_mb, approx = real, False
                cand = {"name": name, "load": None,
                        "vram_used_mb": None, "vram_total_mb": vram_mb,
                        "vram_approx": approx, "temp_c": None,
                        "driver": (card.get("DriverVersion") or "").strip()}
                if best is None or vram_mb > best["vram_total_mb"]:
                    best = cand
            info = best
    except Exception:
        info = None
    _GPU_PROBE.update({"t": time.time(), "info": info, "done": True})
    return info


def gpu_present():
    """True when any usable GPU is visible (NVIDIA, AMD or Intel)."""
    if _find_nvidia_smi():
        return True
    return bool(_generic_gpu())


def detect():
    return {
        "ram_gb": total_ram_gb(),
        "cores": cpu_count(),
        "free_disk_gb": free_disk_gb(),
        "gpu": gpu_present(),
    }


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def _ram():
    return total_ram_gb() or 8.0


def best_tier(category):
    """The most powerful installed-compatible tier of a family for this RAM."""
    ram = _ram()
    best = None
    for t in M.CATALOG:
        if t.category == category and ram >= t.ram_min:
            best = t
    return best.name if best else M.CATALOG[0].name


def recommended_tier():
    return best_tier("general")


def recommendations():
    """Full recommended engine settings for this machine."""
    ram = _ram()
    cores = cpu_count()
    if ram >= 24:
        n_ctx = 16384
    elif ram >= 12:
        n_ctx = 8192
    else:
        n_ctx = 4096
    threads = max(2, min(cores, 8))
    return {
        "tier": recommended_tier(),
        "threads": threads,
        "n_ctx": n_ctx,
        "max_tokens": 1024,
        "temperature": 0.7,
    }


# ---------------------------------------------------------------------------
# Live usage (dashboard « Spécifications & performances »)
# ---------------------------------------------------------------------------

_CPU_SAMPLE = 0.25          # secondes entre les deux mesures de charge CPU


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong)]


def _ft(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def _win_cpu_times():
    """(idle, kernel, user) cumulés, en unités FILETIME, pour toute la machine."""
    idle, kern, user = _FILETIME(), _FILETIME(), _FILETIME()
    ok = ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle),
                                               ctypes.byref(kern),
                                               ctypes.byref(user))
    if not ok:
        return None
    return _ft(idle), _ft(kern), _ft(user)


def _proc_stat_cpu():
    """(idle, total) lus dans /proc/stat (Linux)."""
    with open("/proc/stat") as f:
        parts = f.readline().split()
    values = [int(v) for v in parts[1:11]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return idle, sum(values)


def cpu_percent():
    """Charge CPU de la machine en %, échantillonnée sur un court intervalle.

    Windows : GetSystemTimes (le vrai total machine, comme le gestionnaire de
    tâches). Linux : /proc/stat. Mesurer ``time.process_time()`` ne donnait
    que la charge du processus Python — donc ~0 % en permanence.
    """
    try:
        if sys.platform == "win32":
            first = _win_cpu_times()
            if not first:
                return 0.0
            time.sleep(_CPU_SAMPLE)
            second = _win_cpu_times()
            if not second:
                return 0.0
            d_idle = second[0] - first[0]
            d_total = (second[1] - first[1]) + (second[2] - first[2])
            if d_total <= 0:
                return 0.0
            return round(max(0.0, min(100.0, 100.0 * (d_total - d_idle) / d_total)), 1)
        idle0, total0 = _proc_stat_cpu()
        time.sleep(_CPU_SAMPLE)
        idle1, total1 = _proc_stat_cpu()
        d_total = total1 - total0
        if d_total <= 0:
            return 0.0
        return round(max(0.0, min(100.0,
                                  100.0 * (d_total - (idle1 - idle0)) / d_total)), 1)
    except Exception:
        return 0.0


def process_memory_mb():
    """RSS du processus courant en Mo (Windows / Linux, sans psutil)."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD),
                            ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            # sans argtypes/restype explicites, ctypes tronquerait le HANDLE
            # à 32 bits sur un Python 64 bits et l'appel échouait (0 Mo).
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = ctypes.c_void_p
            psapi = ctypes.windll.psapi
            psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p,
                                                   ctypes.c_void_p,
                                                   ctypes.c_ulong]
            psapi.GetProcessMemoryInfo.restype = ctypes.c_int
            handle = k32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(
                    ctypes.c_void_p(handle), ctypes.byref(counters),
                    ctypes.sizeof(counters)):
                return round(counters.WorkingSetSize / (1024 * 1024), 1)
        else:
            with open(f"/proc/{os.getpid()}/statm") as f:
                pages = int(f.read().split()[1])
            return round(pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024), 1)
    except Exception:
        pass
    return 0.0


def ram_used_gb():
    """RAM utilisée en Go (total - disponible)."""
    try:
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            m = MEMORYSTATUSEX()
            m.dwLength = ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return round((m.ullTotalPhys - m.ullAvailPhys) / (1024 ** 3), 1)
        elif sys.platform.startswith("linux"):
            total = avail = 0
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        avail = int(line.split()[1])
            if total:
                return round((total - avail) / (1024 * 1024), 1)
    except Exception:
        pass
    return 0.0


def gpu_stats():
    """Infos GPU (nom, charge %, VRAM, température) ou None.

    NVIDIA d'abord via nvidia-smi (charge + VRAM + température en direct) ;
    sinon on retombe sur le sondage générique Win32 sans se contenter de
    dire « aucune carte » comme avant.
    """
    exe = _find_nvidia_smi()
    if exe:
        try:
            import subprocess
            out = subprocess.run(
                [exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total,"
                       "temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=8)
            line = (out.stdout or "").strip().splitlines()
            if line:
                parts = [p.strip() for p in line[0].split(",")]
                if len(parts) >= 4:
                    return {
                        "name": parts[0],
                        "load": float(parts[1] or 0),
                        "vram_used_mb": float(parts[2] or 0),
                        "vram_total_mb": float(parts[3] or 0),
                        "temp_c": (float(parts[4])
                                   if len(parts) > 4 and parts[4] else None),
                        "driver": "",
                    }
        except Exception:
            pass
    return _generic_gpu()


def live_stats():
    """Photo instantanée du matériel pour le tableau de bord."""
    total = total_ram_gb() or 0.0
    used = ram_used_gb()
    return {
        "cpu_percent": cpu_percent(),
        "cpu_cores": cpu_count(),
        "ram_used_gb": used,
        "ram_total_gb": round(total, 1),
        "ram_percent": round(100.0 * used / total, 1) if total else 0.0,
        "proc_mb": process_memory_mb(),
        "disk_free_gb": round(free_disk_gb(), 1),
        "gpu": gpu_stats(),
    }


def summary_text():
    info = detect()
    parts = [f"RAM: {info['ram_gb']:.0f} GB" if info["ram_gb"] else "RAM: ?",
             f"CPU: {info['cores']} cores",
             f"Free disk: {info['free_disk_gb']:.1f} GB"]
    gpu = _generic_gpu()
    if gpu and gpu.get("name"):
        vram = gpu.get("vram_total_mb") or 0
        parts.append(f"GPU: {gpu['name']}" +
                     (f" ({'≈' if gpu.get('vram_approx') else ''}{vram:.0f} MB)"
                      if vram else ""))
    elif info["gpu"]:
        parts.append("GPU: NVIDIA")
    else:
        parts.append("GPU: none (CPU inference)")
    return "  ·  ".join(parts)