import sys

# Bibliotecas Windows-only tratadas como opcionais
try:
    import wmi
    import pythoncom
    import win32event
    import win32api
    import winerror
    _HAS_WMI = True
except ImportError:
    _HAS_WMI = False

try:
    import cpuinfo
    _HAS_CPUINFO = True
except ImportError:
    _HAS_CPUINFO = False

import psutil

# ============================================================
# BLOQUEIO DE INSTANCIA UNICA (Windows)
# ============================================================
if _HAS_WMI:
    _mutex = win32event.CreateMutex(None, False, "SekOptimizeMutex")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        sys.exit(0)


# ============================================================
# RAM
# ============================================================
def get_ram_capability():
    if not _HAS_WMI:
        return 0, 0
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        slots = 0
        max_ram_gb = 0
        for arr in c.Win32_PhysicalMemoryArray():
            slots += int(arr.MemoryDevices or 0)
            max_ram_gb += int(arr.MaxCapacity or 0)
        return slots, round(max_ram_gb / (1024 ** 2), 2)
    finally:
        pythoncom.CoUninitialize()


def get_ram_modules():
    if not _HAS_WMI:
        return []
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        modules = []
        for mem in c.Win32_PhysicalMemory():
            modules.append({
                "Slot":           mem.DeviceLocator,
                "Capacidade (GB)": round(int(mem.Capacity) / (1024 ** 3), 2),
                "Velocidade (MHz)": mem.Speed,
                "Fabricante":     mem.Manufacturer,
                "Tipo":           mem.MemoryType,
                "Serial":         mem.SerialNumber,
            })
        return modules
    finally:
        pythoncom.CoUninitialize()


# ============================================================
# CPU
# ============================================================
def get_cpu_info():
    if _HAS_CPUINFO:
        info = cpuinfo.get_cpu_info()
        return {
            "Modelo":         info.get("brand_raw", "N/A"),
            "Arquitetura":    info.get("arch", "N/A"),
            "Bits":           info.get("bits", "N/A"),
            "Frequencia Base": info.get("hz_advertised_friendly", "N/A"),
            "Nucleos":        info.get("count", psutil.cpu_count()),
        }
    import platform
    return {
        "Modelo":         platform.processor(),
        "Arquitetura":    platform.machine(),
        "Bits":           "64",
        "Frequencia Base": "N/A",
        "Nucleos":        psutil.cpu_count(logical=False),
    }


# ============================================================
# GPU
# ============================================================
def get_gpu_info():
    if not _HAS_WMI:
        return []
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        gpus = []
        for gpu in c.Win32_VideoController():
            gpus.append({
                "Nome":     gpu.Name,
                "VRAM (MB)": round(int(gpu.AdapterRAM or 0) / (1024 ** 2), 2),
                "Driver":   gpu.DriverVersion,
            })
        return gpus
    finally:
        pythoncom.CoUninitialize()


# ============================================================
# DISCOS
# ============================================================
def get_disks():
    if not _HAS_WMI:
        return []
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        disks = []
        for d in c.Win32_DiskDrive():
            disks.append({
                "Modelo":      d.Model,
                "Interface":   d.InterfaceType,
                "Tamanho (GB)": round(int(d.Size or 0) / (1024 ** 3), 2),
                "Serial":      d.SerialNumber,
            })
        return disks
    finally:
        pythoncom.CoUninitialize()