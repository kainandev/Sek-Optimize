import json
import csv
import io
import os
import re
import sys
import platform
import socket
import getpass
import subprocess
import winreg
from datetime import datetime, timedelta

from util.report_html import render_report

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

try:
    import wmi
    import pythoncom
    _HAS_WMI = True
except ImportError:
    _HAS_WMI = False

try:
    import cpuinfo
    _HAS_CPUINFO = True
except ImportError:
    _HAS_CPUINFO = False

try:
    import win32evtlog
    import win32evtlogutil
    import win32security
    import win32api
    _HAS_EVTLOG = True
except ImportError:
    _HAS_EVTLOG = False


# Version bumped when new top-level keys are added to the schema.
SCHEMA_VERSION = "0.5"

# Readable labels for WMI memory type codes (Win32_PhysicalMemory.MemoryType)
_RAM_TYPE = {
    0: "Unknown", 1: "Other", 2: "DRAM", 3: "Sync DRAM",
    4: "Cache DRAM", 5: "EDO", 6: "EDRAM", 7: "VRAM", 8: "SRAM",
    9: "RAM", 10: "ROM", 11: "Flash", 12: "EEPROM", 13: "FEPROM",
    14: "EPROM", 15: "CDRAM", 16: "3DRAM", 17: "SDRAM", 18: "SGRAM",
    19: "RDRAM", 20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM",
    24: "DDR3", 26: "DDR4", 27: "LPDDR", 28: "LPDDR2",
    29: "LPDDR3", 30: "LPDDR4",
}

# Readable labels for WMI form factor codes (Win32_PhysicalMemory.FormFactor)
_RAM_FORM = {
    0: "Unknown", 1: "Other", 2: "SIP", 3: "DIP", 4: "ZIP",
    5: "SOJ", 6: "Proprietary", 7: "SIMM", 8: "DIMM", 9: "TSOP",
    10: "PGA", 11: "RIMM", 12: "SODIMM", 13: "SRIMM", 14: "SMD",
    15: "SSMP", 16: "QFP", 17: "TQFP", 18: "SOIC", 19: "LCC",
    20: "PLCC", 21: "BGA", 22: "FPBGA", 23: "LGA",
}

# Readable labels for MSFT_PhysicalDisk.MediaType (root\Microsoft\Windows\Storage)
_DISK_MEDIA_TYPE = {0: "Nao especificado", 3: "HDD", 4: "SSD", 5: "SCM"}

# Readable labels for MSFT_PhysicalDisk.HealthStatus
_DISK_HEALTH_STATUS = {0: "Saudavel", 1: "Aviso", 2: "Nao Saudavel", 5: "Desconhecido"}

# Readable labels for MSFT_PhysicalDisk.BusType (subset of STORAGE_BUS_TYPE
# actually seen on consumer hardware; anything else falls back to "Outro")
_DISK_BUS_TYPE = {
    1: "SCSI", 2: "ATAPI", 3: "ATA", 4: "IEEE1394", 7: "USB",
    8: "RAID", 9: "iSCSI", 10: "SAS", 11: "SATA", 17: "NVMe",
}

# Registry hives searched for installed programs
_UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]

# Registry hives searched for startup entries
_STARTUP_KEYS = [
    (winreg.HKEY_CURRENT_USER,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Run"),
]

# Known antivirus product display-name substrings (case-insensitive)
_AV_KEYWORDS = [
    "antivirus", "anti-virus", "defender", "kaspersky", "avast", "avg",
    "bitdefender", "norton", "mcafee", "eset", "malwarebytes", "trend micro",
    "sophos", "webroot", "comodo", "f-secure", "g data", "bullguard",
    "avira", "panda", "vipre", "cylance", "crowdstrike", "sentinelone",
    "carbon black", "symantec", "security essentials",
]

# Known email client display-name substrings and their profile registry paths
_EMAIL_CLIENTS = {
    "Microsoft Outlook": {
        "keywords": ["outlook"],
        "profile_roots": [
            r"SOFTWARE\Microsoft\Office\16.0\Outlook\Profiles",
            r"SOFTWARE\Microsoft\Office\15.0\Outlook\Profiles",
            r"SOFTWARE\Microsoft\Office\14.0\Outlook\Profiles",
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows Messaging Subsystem\Profiles",
        ],
    },
    "Mozilla Thunderbird": {
        "keywords": ["thunderbird"],
        "profile_roots": [],  # profiles.ini parsed from filesystem
    },
    "eM Client": {
        "keywords": ["em client"],
        "profile_roots": [],
    },
    "The Bat!": {
        "keywords": ["the bat"],
        "profile_roots": [],
    },
    "Mailbird": {
        "keywords": ["mailbird"],
        "profile_roots": [],
    },
    "Spike": {
        "keywords": ["spike"],
        "profile_roots": [],
    },
    "Windows Mail": {
        "keywords": ["windows mail", "microsoft mail"],
        "profile_roots": [],
    },
}


class SchemeBuilder:
    """
    Collects hardware and software inventory data and serializes it
    to JSON, CSV, or HTML. Operates independently with no base class.
    Uses WMI for deep hardware introspection when available.
    """

    # ============================================================
    # PUBLIC ENTRY POINT
    # ============================================================
    def collect(self):
        """
        Returns a fully structured dictionary with machine inventory.
        Sections: system, bios, motherboard, cpu, memory, storage,
                  disk_health, gpu, network, open_ports, audio, software,
                  installed_programs, startup_programs, local_users,
                  antivirus, email_clients, event_log, runtime.
        """
        return {
            "schema_version":     SCHEMA_VERSION,
            "generated_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "system":             self._collect_system(),
            "bios":               self._collect_bios(),
            "motherboard":        self._collect_motherboard(),
            "cpu":                self._collect_cpu(),
            "memory":             self._collect_memory(),
            "storage":            self._collect_storage(),
            "disk_health":        self._collect_disk_health(),
            "gpu":                self._collect_gpu(),
            "network":            self._collect_network(),
            "open_ports":         self._collect_open_ports(),
            "audio":              self._collect_audio(),
            "software":           self._collect_software(),
            "installed_programs": self._collect_installed_programs(),
            "startup_programs":   self._collect_startup_programs(),
            "local_users":        self._collect_local_users(),
            "antivirus":          self._collect_antivirus(),
            "email_clients":      self._collect_email_clients(),
            "event_log":          self._collect_event_log(),
            "runtime":            self._collect_runtime(),
        }

    # ============================================================
    # SYSTEM
    # ============================================================
    def _collect_system(self):
        d = {
            "hostname":        socket.gethostname(),
            "username":        getpass.getuser(),
            "os":              platform.system(),
            "os_release":      platform.release(),
            "os_version":      platform.version(),
            "os_architecture": platform.machine(),
            "boot_mode":       self._get_boot_mode(),
        }
        if _HAS_PSUTIL:
            boot_dt        = datetime.fromtimestamp(psutil.boot_time())
            uptime_sec     = (datetime.now() - boot_dt).total_seconds()
            h, rem         = divmod(int(uptime_sec), 3600)
            m, s           = divmod(rem, 60)
            d["boot_time"] = boot_dt.strftime("%Y-%m-%d %H:%M:%S")
            d["uptime"]    = f"{h:02d}h {m:02d}m {s:02d}s"
            d["processes"] = len(psutil.pids())

        # OS install date, serial, build, edition, and license type via WMI
        if _HAS_WMI:
            try:
                pythoncom.CoInitialize()
                c = wmi.WMI()
                for os_obj in c.Win32_OperatingSystem():
                    raw = str(os_obj.InstallDate or "")
                    if len(raw) >= 8:
                        d["os_install_date"] = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
                    d["os_serial"]           = str(os_obj.SerialNumber   or "N/A")
                    d["os_build"]            = str(os_obj.BuildNumber    or "N/A")
                    d["os_registered_to"]    = str(os_obj.RegisteredUser or "N/A")
                    caption = str(os_obj.Caption or "")
                    d["os_edition"]          = caption
                    d["os_license_type"]     = self._parse_license_type(caption)
                    break
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        return d

    def _parse_license_type(self, caption):
        """
        Extracts the edition/license type from the OS caption string.
        Ordered by specificity so longer tokens are matched first.
        Returns 'Unknown' if no known edition keyword is found.
        """
        known_editions = [
            "Enterprise LTSC", "Enterprise N", "Enterprise",
            "Education N", "Education",
            "Pro for Workstations", "Pro N", "Pro",
            "Home Single Language", "Home N", "Home",
            "S Mode", "SE", "IoT",
        ]
        for edition in known_editions:
            if edition.lower() in caption.lower():
                return edition
        return "Unknown"

    def _get_boot_mode(self):
        # Presence of SecureBoot.exe or the EFI subdirectory confirms UEFI
        if os.path.exists(r"C:\Windows\System32\SecureBoot.exe"):
            return "UEFI"
        if os.path.isdir(r"C:\Windows\System32\Microsoft\Efi"):
            return "UEFI"
        return "Legacy BIOS"

    # ============================================================
    # BIOS
    # ============================================================
    def _collect_bios(self):
        d = {}
        if not _HAS_WMI:
            return d
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            for bios in c.Win32_BIOS():
                d["vendor"]         = str(bios.Manufacturer        or "N/A")
                d["version"]        = str(bios.SMBIOSBIOSVersion   or "N/A")
                d["release_date"]   = str(bios.ReleaseDate         or "N/A")[:8]
                d["serial_number"]  = str(bios.SerialNumber        or "N/A")
                d["smbios_version"] = (
                    f"{bios.SMBIOSMajorVersion}.{bios.SMBIOSMinorVersion}"
                    if bios.SMBIOSMajorVersion else "N/A"
                )
                break
        except Exception:
            pass
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        return d

    # ============================================================
    # MOTHERBOARD
    # ============================================================
    def _collect_motherboard(self):
        d = {}
        if not _HAS_WMI:
            return d
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            for mb in c.Win32_BaseBoard():
                d["manufacturer"]  = str(mb.Manufacturer or "N/A")
                d["model"]         = str(mb.Product      or "N/A")
                d["serial_number"] = str(mb.SerialNumber or "N/A")
                d["version"]       = str(mb.Version      or "N/A")
                break
        except Exception:
            pass
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        return d

    # ============================================================
    # CPU
    # ============================================================
    def _collect_cpu(self):
        d = {
            "architecture": platform.machine(),
            "processor":    platform.processor(),
        }
        if _HAS_PSUTIL:
            d["physical_cores"] = psutil.cpu_count(logical=False)
            d["logical_cores"]  = psutil.cpu_count(logical=True)
            freq = psutil.cpu_freq()
            if freq:
                d["frequency_current_mhz"] = round(freq.current, 0)
                d["frequency_min_mhz"]     = round(freq.min, 0)
                d["frequency_max_mhz"]     = round(freq.max, 0)

        if _HAS_CPUINFO:
            try:
                info = cpuinfo.get_cpu_info()
                d["model"]          = info.get("brand_raw",              "N/A")
                d["vendor_id"]      = info.get("vendor_id_raw",          "N/A")
                d["bits"]           = info.get("bits",                   "N/A")
                d["frequency_base"] = info.get("hz_advertised_friendly", "N/A")
                d["l2_cache_size"]  = info.get("l2_cache_size",          "N/A")
                d["l3_cache_size"]  = info.get("l3_cache_size",          "N/A")
                d["stepping"]       = info.get("stepping",               "N/A")
                d["model_id"]       = info.get("model",                  "N/A")
                d["family"]         = info.get("family",                 "N/A")
                d["flags"]          = info.get("flags",                  [])
            except Exception:
                pass

        if _HAS_WMI:
            try:
                pythoncom.CoInitialize()
                c = wmi.WMI()
                for cpu in c.Win32_Processor():
                    d["socket"]         = str(cpu.SocketDesignation or "N/A")
                    d["manufacturer"]   = str(cpu.Manufacturer      or "N/A")
                    d["max_clock_mhz"]  = str(cpu.MaxClockSpeed     or "N/A")
                    d["l2_cache_kb"]    = str(cpu.L2CacheSize       or "N/A")
                    d["l3_cache_kb"]    = str(cpu.L3CacheSize       or "N/A")
                    d["processor_id"]   = str(cpu.ProcessorId       or "N/A").strip()
                    d["virtualization"] = (
                        "Enabled"
                        if getattr(cpu, "VirtualizationFirmwareEnabled", False)
                        else "Disabled"
                    )
                    break
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        return d

    # ============================================================
    # MEMORY
    # ============================================================
    def _collect_memory(self):
        d = {}
        if _HAS_PSUTIL:
            vm = psutil.virtual_memory()
            sw = psutil.swap_memory()
            d["total_gb"]       = round(vm.total     / (1024 ** 3), 2)
            d["available_gb"]   = round(vm.available / (1024 ** 3), 2)
            d["used_gb"]        = round(vm.used      / (1024 ** 3), 2)
            d["usage_pct"]      = vm.percent
            d["swap_total_gb"]  = round(sw.total / (1024 ** 3), 2)
            d["swap_used_gb"]   = round(sw.used  / (1024 ** 3), 2)
            d["swap_usage_pct"] = sw.percent

        if _HAS_WMI:
            try:
                pythoncom.CoInitialize()
                c = wmi.WMI()

                slots   = 0
                max_ram = 0
                for arr in c.Win32_PhysicalMemoryArray():
                    slots   += int(arr.MemoryDevices or 0)
                    max_ram += int(arr.MaxCapacity   or 0)

                d["total_slots"]      = slots
                d["max_supported_gb"] = round(max_ram / (1024 ** 2), 2)

                modules = []
                for m in c.Win32_PhysicalMemory():
                    modules.append({
                        "slot":           str(m.DeviceLocator or "N/A"),
                        "bank":           str(m.BankLabel     or "N/A"),
                        "capacity_gb":    round(int(m.Capacity or 0) / (1024 ** 3), 2),
                        "speed_mhz":      str(m.Speed or "N/A"),
                        "configured_mhz": str(m.ConfiguredClockSpeed or "N/A"),
                        "type":           _RAM_TYPE.get(int(m.MemoryType or 0), "Unknown"),
                        "form_factor":    _RAM_FORM.get(int(m.FormFactor or 0), "Unknown"),
                        "manufacturer":   str(m.Manufacturer or "N/A"),
                        "part_number":    str(m.PartNumber   or "N/A").strip(),
                        "serial_number":  str(m.SerialNumber or "N/A"),
                        "voltage_mv":     str(m.ConfiguredVoltage or "N/A"),
                    })
                d["modules"] = modules
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        return d

    # ============================================================
    # STORAGE
    # ============================================================
    def _collect_storage(self):
        drives  = []
        volumes = []

        if _HAS_WMI:
            try:
                pythoncom.CoInitialize()
                c = wmi.WMI()
                for disk in c.Win32_DiskDrive():
                    drives.append({
                        "model":            str(disk.Model            or "N/A"),
                        "interface":        str(disk.InterfaceType    or "N/A"),
                        "media_type":       str(disk.MediaType        or "N/A"),
                        "size_gb":          round(int(disk.Size or 0) / (1024 ** 3), 2),
                        "partitions":       int(disk.Partitions       or 0),
                        "serial_number":    str(disk.SerialNumber     or "N/A").strip(),
                        "firmware":         str(disk.FirmwareRevision or "N/A"),
                        "bytes_per_sector": int(disk.BytesPerSector   or 0),
                    })
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        if _HAS_PSUTIL:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    volumes.append({
                        "mount_point": part.mountpoint,
                        "filesystem":  part.fstype,
                        "total_gb":    round(usage.total / (1024 ** 3), 2),
                        "used_gb":     round(usage.used  / (1024 ** 3), 2),
                        "free_gb":     round(usage.free  / (1024 ** 3), 2),
                        "usage_pct":   usage.percent,
                    })
                except (PermissionError, OSError):
                    pass

        return {"drives": drives, "volumes": volumes}

    # ============================================================
    # DISK HEALTH (SMART-equivalent via Storage Reliability Counters)
    #
    # MSFT_PhysicalDisk (root\Microsoft\Windows\Storage) gives basic
    # health/media info without elevation. MSFT_StorageReliabilityCounter
    # adds wear %, power-on hours and temperature but requires the process
    # to be running elevated - Sek Optimize always relaunches itself as
    # administrator (see main.py), so this is expected to succeed there;
    # it degrades gracefully (per-disk note) when it doesn't.
    # ============================================================
    def _collect_disk_health(self):
        disks = []
        if not _HAS_WMI:
            return disks
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI(namespace=r"root\Microsoft\Windows\Storage")

            reliability = {}
            try:
                for r in c.MSFT_StorageReliabilityCounter():
                    reliability[str(r.DeviceId)] = r
            except Exception:
                pass

            for d in c.MSFT_PhysicalDisk():
                device_id = str(d.DeviceId)
                entry = {
                    "device_id":     device_id,
                    "model":         str(d.FriendlyName or "N/A"),
                    "serial_number": str(getattr(d, "SerialNumber", "") or "N/A"),
                    "media_type":    _DISK_MEDIA_TYPE.get(int(d.MediaType or 0), "Desconhecido"),
                    "bus_type":      _DISK_BUS_TYPE.get(int(getattr(d, "BusType", 0) or 0), "Outro"),
                    "size_gb":       round(int(d.Size or 0) / (1024 ** 3), 2),
                    "health_status": _DISK_HEALTH_STATUS.get(int(d.HealthStatus or 0), "Desconhecido"),
                }

                rel = reliability.get(device_id)
                if rel is not None:
                    wear = getattr(rel, "Wear", None)
                    poh  = getattr(rel, "PowerOnHours", None)
                    temp = getattr(rel, "Temperature", None)

                    entry["wear_pct"]              = int(wear) if wear is not None else None
                    entry["life_remaining_pct"]     = (100 - int(wear)) if wear is not None else None
                    entry["temperature_c"]          = int(temp) if temp is not None else None
                    entry["temperature_max_c"]      = getattr(rel, "TemperatureMax", None)
                    entry["power_on_hours"]         = int(poh) if poh is not None else None
                    entry["power_on_days"]          = round(int(poh) / 24, 1) if poh is not None else None
                    entry["read_errors_uncorrected"] = getattr(rel, "ReadErrorsUncorrected", None)
                    entry["write_errors_uncorrected"] = getattr(rel, "WriteErrorsUncorrected", None)
                    entry["start_stop_count"]       = getattr(rel, "StartStopCycleCount", None)
                else:
                    entry["reliability_unavailable"] = (
                        "Requer privilegios de administrador para detalhar "
                        "desgaste, horas ligado e temperatura (SMART)."
                    )

                disks.append(entry)
        except Exception:
            pass
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        return disks

    # ============================================================
    # EVENT LOG (Visualizador de Eventos do Windows)
    #
    # System/Application: todos os eventos de Erro e Aviso na janela de
    # tempo configurada (nunca so uma amostra - o total real e sempre
    # contado via 'total_matched', mesmo quando a lista de entradas e
    # limitada por 'max_per_log' para nao inflar o relatorio).
    # Security: exige SeSecurityPrivilege (mesmo elevado, o privilegio
    # vem desabilitado por padrao no token) - habilitado explicitamente
    # aqui; se a politica local ainda assim negar, o log e reportado com
    # 'error' em vez de derrubar a coleta inteira.
    # ============================================================
    _EVENT_LOG_WINDOW_DAYS = 14
    _EVENT_LOG_MAX_ENTRIES = 500

    def _collect_event_log(self):
        if not _HAS_EVTLOG:
            return {}

        try:
            self._enable_privilege(win32security.SE_SECURITY_NAME)
        except Exception:
            pass

        level_filters = {
            "System":      {win32evtlog.EVENTLOG_ERROR_TYPE, win32evtlog.EVENTLOG_WARNING_TYPE},
            "Application": {win32evtlog.EVENTLOG_ERROR_TYPE, win32evtlog.EVENTLOG_WARNING_TYPE},
            "Security":    {win32evtlog.EVENTLOG_AUDIT_FAILURE},
        }
        level_labels = {
            win32evtlog.EVENTLOG_ERROR_TYPE:       "Erro",
            win32evtlog.EVENTLOG_WARNING_TYPE:      "Aviso",
            win32evtlog.EVENTLOG_INFORMATION_TYPE:  "Informacao",
            win32evtlog.EVENTLOG_AUDIT_SUCCESS:     "Auditoria (Sucesso)",
            win32evtlog.EVENTLOG_AUDIT_FAILURE:     "Auditoria (Falha)",
        }

        cutoff = datetime.now() - timedelta(days=self._EVENT_LOG_WINDOW_DAYS)
        result = {}

        for log_name, wanted_types in level_filters.items():
            entries      = []
            by_source    = {}
            total_matched = 0
            try:
                hand = win32evtlog.OpenEventLog(None, log_name)
            except Exception as e:
                result[log_name] = {"error": str(e), "entries": [], "total_matched": 0, "by_source": {}}
                continue

            try:
                flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
                stop = False
                while not stop:
                    records = win32evtlog.ReadEventLog(hand, flags, 0)
                    if not records:
                        break
                    for ev in records:
                        if ev.TimeGenerated < cutoff:
                            stop = True
                            break
                        if ev.EventType not in wanted_types:
                            continue

                        total_matched += 1
                        source = str(ev.SourceName or "N/A")
                        by_source[source] = by_source.get(source, 0) + 1

                        if len(entries) < self._EVENT_LOG_MAX_ENTRIES:
                            try:
                                msg = win32evtlogutil.SafeFormatMessage(ev, log_name)
                            except Exception:
                                msg = " ".join(str(s) for s in (ev.StringInserts or []))
                            entries.append({
                                "time":     ev.TimeGenerated.strftime("%Y-%m-%d %H:%M:%S"),
                                "level":    level_labels.get(ev.EventType, str(ev.EventType)),
                                "source":   source,
                                "event_id": ev.EventID & 0xFFFF,
                                "message":  (msg or "").strip()[:500],
                            })
            except Exception as e:
                result.setdefault(log_name, {})["error"] = str(e)
            finally:
                win32evtlog.CloseEventLog(hand)

            result[log_name] = {
                "window_days":   self._EVENT_LOG_WINDOW_DAYS,
                "total_matched": total_matched,
                "shown":         len(entries),
                "by_source":     dict(sorted(by_source.items(), key=lambda kv: kv[1], reverse=True)),
                "entries":       entries,
            }

        return result

    def _enable_privilege(self, name):
        """Habilita um privilegio no token do processo atual (ex.: SeSecurityPrivilege
        para ler o log de Seguranca) - presente mas desabilitado por padrao mesmo
        rodando elevado."""
        htoken = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(),
            win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY,
        )
        priv_id = win32security.LookupPrivilegeValue(None, name)
        win32security.AdjustTokenPrivileges(htoken, False, [(priv_id, win32security.SE_PRIVILEGE_ENABLED)])

    # ============================================================
    # GPU
    # ============================================================
    def _collect_gpu(self):
        gpus = []
        if not _HAS_WMI:
            return gpus
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            for gpu in c.Win32_VideoController():
                gpus.append({
                    "name":            str(gpu.Name                  or "N/A"),
                    "adapter_ram_mb":  round(int(gpu.AdapterRAM or 0) / (1024 ** 2), 0),
                    "driver_version":  str(gpu.DriverVersion          or "N/A"),
                    "driver_date":     str(gpu.DriverDate             or "N/A")[:8],
                    "video_processor": str(gpu.VideoProcessor         or "N/A"),
                    "video_mode":      str(gpu.VideoModeDescription   or "N/A"),
                    "current_bpp":     str(gpu.CurrentBitsPerPixel    or "N/A"),
                    "current_hz":      str(gpu.CurrentRefreshRate     or "N/A"),
                    "status":          str(gpu.Status                 or "N/A"),
                    "pnp_device_id":   str(gpu.PNPDeviceID            or "N/A"),
                })
        except Exception:
            pass
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        return gpus

    # ============================================================
    # NETWORK
    # ============================================================
    def _collect_network(self):
        adapters = []
        if _HAS_WMI:
            try:
                pythoncom.CoInitialize()
                c = wmi.WMI()
                for nic in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
                    adapters.append({
                        "description":     str(nic.Description or "N/A"),
                        "mac_address":     str(nic.MACAddress  or "N/A"),
                        "ip_addresses":    list(nic.IPAddress            or []),
                        "subnets":         list(nic.IPSubnet             or []),
                        "default_gateway": list(nic.DefaultIPGateway     or []),
                        "dns_servers":     list(nic.DNSServerSearchOrder or []),
                        "dhcp_enabled":    bool(nic.DHCPEnabled),
                        "dhcp_server":     str(nic.DHCPServer or "N/A"),
                    })
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        counters = {}
        if _HAS_PSUTIL:
            try:
                net = psutil.net_io_counters()
                counters = {
                    "bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 2),
                    "bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 2),
                    "packets_sent":  net.packets_sent,
                    "packets_recv":  net.packets_recv,
                    "errors_out":    net.errout,
                    "errors_in":     net.errin,
                }
            except Exception:
                pass

        return {"adapters": adapters, "counters": counters}

    # ============================================================
    # OPEN PORTS
    # Lists all TCP/UDP ports currently in LISTEN state.
    # psutil is used when available; falls back to netstat parsing.
    # ============================================================
    def _collect_open_ports(self):
        ports = []

        if _HAS_PSUTIL:
            try:
                # Collect process name map once to avoid per-connection lookups
                pid_names = {}
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        pid_names[proc.info["pid"]] = proc.info["name"]
                    except Exception:
                        pass

                seen = set()
                for conn in psutil.net_connections(kind="inet"):
                    if conn.status not in ("LISTEN", "NONE") and conn.type == 1:
                        # type 1 = SOCK_STREAM (TCP); include all UDP (no status)
                        continue
                    # For UDP (type 2) there is no status field
                    laddr = conn.laddr
                    if not laddr:
                        continue
                    key = (laddr.port, conn.type)
                    if key in seen:
                        continue
                    seen.add(key)
                    proto = "TCP" if conn.type == 1 else "UDP"
                    ports.append({
                        "protocol":    proto,
                        "local_port":  laddr.port,
                        "local_addr":  laddr.ip,
                        "pid":         conn.pid or 0,
                        "process":     pid_names.get(conn.pid, "N/A"),
                    })
                ports.sort(key=lambda x: x["local_port"])
            except Exception:
                pass

        # Fallback: parse netstat output when psutil is unavailable
        if not ports:
            try:
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, timeout=10,
                )
                for line in result.stdout.decode("utf-8", errors="replace").splitlines():
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    proto = parts[0].upper()
                    if proto not in ("TCP", "UDP"):
                        continue
                    state = parts[3] if proto == "TCP" and len(parts) > 3 else "LISTEN"
                    if "LISTEN" not in state.upper():
                        continue
                    try:
                        local_port = int(parts[1].rsplit(":", 1)[-1])
                    except ValueError:
                        continue
                    ports.append({
                        "protocol":   proto,
                        "local_port": local_port,
                        "local_addr": parts[1].rsplit(":", 1)[0],
                        "pid":        int(parts[-1]) if parts[-1].isdigit() else 0,
                        "process":    "N/A",
                    })
            except Exception:
                pass

        return ports

    # ============================================================
    # AUDIO
    # ============================================================
    def _collect_audio(self):
        devices = []
        if not _HAS_WMI:
            return devices
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            for dev in c.Win32_SoundDevice():
                devices.append({
                    "name":           str(dev.Name         or "N/A"),
                    "manufacturer":   str(dev.Manufacturer or "N/A"),
                    "status":         str(dev.Status       or "N/A"),
                    "pnp_device_id":  str(dev.PNPDeviceID  or "N/A"),
                })
        except Exception:
            pass
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        return devices

    # ============================================================
    # SOFTWARE (Python runtime + app metadata)
    # ============================================================
    def _collect_software(self):
        return {
            "python_version":  platform.python_version(),
            "python_build":    " ".join(platform.python_build()),
            "python_compiler": platform.python_compiler(),
            "executable_type": (
                "EXE (PyInstaller)"
                if getattr(sys, "frozen", False)
                else "Script (.py)"
            ),
            "base_directory":  os.getcwd(),
            "app_name":        "Sek Optimize",
        }

    # ============================================================
    # INSTALLED PROGRAMS
    # Reads all three Uninstall registry hives to cover 32-bit,
    # 64-bit, and per-user installations. Skips entries without
    # a display name (system components, patches, etc.).
    # ============================================================
    def _collect_installed_programs(self):
        programs = []
        seen     = set()

        for hive, key_path in _UNINSTALL_KEYS:
            try:
                key = winreg.OpenKey(hive, key_path)
            except OSError:
                continue
            try:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(key, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        sub = winreg.OpenKey(key, sub_name)
                        name    = self._reg_str(sub, "DisplayName")
                        version = self._reg_str(sub, "DisplayVersion")
                        vendor  = self._reg_str(sub, "Publisher")
                        date    = self._reg_str(sub, "InstallDate")
                        size_kb = self._reg_int(sub, "EstimatedSize")
                        winreg.CloseKey(sub)

                        if not name or name in seen:
                            continue
                        seen.add(name)

                        programs.append({
                            "name":        name,
                            "version":     version or "N/A",
                            "vendor":      vendor  or "N/A",
                            "install_date":date    or "N/A",
                            "size_kb":     size_kb,
                        })
                    except Exception:
                        pass
            finally:
                winreg.CloseKey(key)

        programs.sort(key=lambda x: x["name"].lower())
        return programs

    # ============================================================
    # STARTUP PROGRAMS
    # Reads the Run keys from HKCU and HKLM (both 32 and 64-bit).
    # Each value under a Run key is one startup entry.
    # ============================================================
    def _collect_startup_programs(self):
        entries = []
        seen    = set()

        for hive, key_path in _STARTUP_KEYS:
            hive_label = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
            try:
                key = winreg.OpenKey(hive, key_path)
            except OSError:
                continue
            try:
                i = 0
                while True:
                    try:
                        name, data, _ = winreg.EnumValue(key, i)
                        i += 1
                    except OSError:
                        break
                    uid = f"{hive_label}:{name}"
                    if uid in seen:
                        continue
                    seen.add(uid)
                    entries.append({
                        "name":    name,
                        "command": str(data),
                        "hive":    hive_label,
                        "key":     key_path,
                    })
            finally:
                winreg.CloseKey(key)

        entries.sort(key=lambda x: x["name"].lower())
        return entries

    # ============================================================
    # LOCAL USERS
    # Uses WMI Win32_UserAccount for local accounts only.
    # Falls back to 'net user' shell output when WMI is unavailable.
    # ============================================================
    def _collect_local_users(self):
        users = []

        if _HAS_WMI:
            try:
                pythoncom.CoInitialize()
                c = wmi.WMI()
                for u in c.Win32_UserAccount(LocalAccount=True):
                    users.append({
                        "name":        str(u.Name        or "N/A"),
                        "full_name":   str(u.FullName    or "N/A"),
                        "description": str(u.Description or "N/A"),
                        "sid":         str(u.SID         or "N/A"),
                        "disabled":    bool(u.Disabled),
                        "locked_out":  bool(u.Lockout),
                        "status":      str(u.Status      or "N/A"),
                        "account_type": self._account_type_label(
                            getattr(u, "AccountType", 0) or 0),
                    })
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        # Fallback: parse 'net user' output
        if not users:
            try:
                result = subprocess.run(
                    ["net", "user"],
                    capture_output=True, timeout=10,
                )
                lines = result.stdout.decode("cp850", errors="replace").splitlines()
                for line in lines:
                    if line.startswith("-") or line.startswith("The") or not line.strip():
                        continue
                    for name in line.split():
                        if name:
                            users.append({
                                "name":        name,
                                "full_name":   "N/A",
                                "description": "N/A",
                                "sid":         "N/A",
                                "disabled":    False,
                                "locked_out":  False,
                                "status":      "N/A",
                                "account_type":"N/A",
                            })
            except Exception:
                pass

        return users

    def _account_type_label(self, account_type):
        """Translates Win32_UserAccount.AccountType bitmask to a readable label."""
        labels = []
        if account_type & 0x200:
            labels.append("Domain")
        if account_type & 0x001:
            labels.append("Temporary Duplicate")
        if account_type & 0x002:
            labels.append("Normal")
        if account_type & 0x004:
            labels.append("Interdomain Trust")
        if account_type & 0x008:
            labels.append("Workstation Trust")
        if account_type & 0x010:
            labels.append("Server Trust")
        return ", ".join(labels) if labels else "Unknown"

    # ============================================================
    # ANTIVIRUS
    # Queries the Windows Security Center (WMI SecurityCenter2
    # namespace) which enumerates registered AV products.
    # Falls back to scanning the installed programs list for
    # well-known antivirus display names.
    # ============================================================
    def _collect_antivirus(self):
        av_list = []

        # Primary source: Windows Security Center namespace
        if _HAS_WMI:
            try:
                pythoncom.CoInitialize()
                # SecurityCenter2 is available on Vista+ for the local machine
                c = wmi.WMI(namespace=r"root\SecurityCenter2")
                for av in c.AntiVirusProduct():
                    # productState encodes enabled/updated status as a bitmask
                    state      = int(getattr(av, "productState", 0) or 0)
                    enabled    = bool((state >> 12) & 0xF != 0)
                    up_to_date = bool((state >> 4)  & 0xF == 0)
                    av_list.append({
                        "name":          str(av.displayName        or "N/A"),
                        "instance_guid": str(av.instanceGuid       or "N/A"),
                        "path":          str(getattr(av, "pathToSignedProductExe", "N/A") or "N/A"),
                        "enabled":       enabled,
                        "up_to_date":    up_to_date,
                        "source":        "SecurityCenter2",
                    })
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        # Fallback / supplement: scan installed programs
        if not av_list:
            try:
                programs = self._collect_installed_programs()
                for prog in programs:
                    name_lower = prog["name"].lower()
                    if any(kw in name_lower for kw in _AV_KEYWORDS):
                        av_list.append({
                            "name":          prog["name"],
                            "instance_guid": "N/A",
                            "path":          "N/A",
                            "enabled":       None,
                            "up_to_date":    None,
                            "source":        "InstalledPrograms",
                        })
            except Exception:
                pass

        return av_list

    # ============================================================
    # EMAIL CLIENTS
    # Detects installed email clients by cross-referencing the
    # installed programs list. For Outlook, reads registered profiles
    # and the MAPI account names from the registry. For Thunderbird,
    # parses the profiles.ini file on disk.
    # ============================================================
    def _collect_email_clients(self):
        results = []

        installed_names = []
        try:
            installed_names = [
                p["name"] for p in self._collect_installed_programs()
            ]
        except Exception:
            pass

        for client_label, meta in _EMAIL_CLIENTS.items():
            keywords = meta["keywords"]
            found    = any(
                any(kw in inst.lower() for kw in keywords)
                for inst in installed_names
            )

            # Office suites rarely list "Outlook" by name in Add/Remove
            # Programs (e.g. "Microsoft Office Professional Plus 2016"),
            # so fall back to the App Paths registry entry Outlook always
            # registers regardless of the bundling product's display name.
            if client_label == "Microsoft Outlook" and not found:
                found = self._outlook_app_path_exists()

            if not found:
                continue

            entry = {
                "client":   client_label,
                "accounts": [],
            }

            # --- Outlook: registry profiles ---
            if client_label == "Microsoft Outlook":
                for prof_root in meta["profile_roots"]:
                    accounts = self._outlook_accounts_from_registry(
                        winreg.HKEY_CURRENT_USER, prof_root)
                    if accounts:
                        entry["accounts"].extend(accounts)
                        break

            # --- Thunderbird: profiles.ini ---
            elif client_label == "Mozilla Thunderbird":
                entry["accounts"] = self._thunderbird_accounts()

            results.append(entry)

        return results

    def _outlook_app_path_exists(self):
        """
        Checks the App Paths registry entry Outlook always registers on
        install, independent of the Office product's display name.
        """
        for key_path in (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE",
        ):
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                winreg.CloseKey(key)
                return True
            except OSError:
                continue
        return False

    def _outlook_accounts_from_registry(self, hive, profiles_path):
        """
        Walks HKCU\...\Profiles\<profile>\9375CFF0... to extract
        account display names and email addresses stored by Outlook.

        Modern Outlook (2016+) stores the address under "Account Name"
        rather than the legacy "Email"/"SMTP Email Address" fields, and
        also lists non-mail services (e.g. the Outlook Address Book) under
        the same subkey tree, so entries are kept only when an address is
        actually resolvable.
        """
        accounts = []
        try:
            profiles_key = winreg.OpenKey(hive, profiles_path)
        except OSError:
            return accounts

        # Account data lives inside a subkey whose name starts with 9375CFF0
        _ACCOUNT_SUBKEY = "9375CFF0413111d3B88A00104B2A6676"

        try:
            i = 0
            while True:
                try:
                    profile_name = winreg.EnumKey(profiles_key, i)
                    i += 1
                except OSError:
                    break
                try:
                    acct_key_path   = f"{profiles_path}\\{profile_name}\\{_ACCOUNT_SUBKEY}"
                    acct_root       = winreg.OpenKey(hive, acct_key_path)
                    seen_in_profile = set()
                    j = 0
                    while True:
                        try:
                            acct_sub = winreg.EnumKey(acct_root, j)
                            j += 1
                        except OSError:
                            break
                        try:
                            sub = winreg.OpenKey(acct_root, acct_sub)
                            display  = self._reg_str(sub, "Display Name")
                            email    = self._reg_str(sub, "Email")
                            smtp     = self._reg_str(sub, "SMTP Email Address")
                            acct_nm  = self._reg_str(sub, "Account Name")
                            winreg.CloseKey(sub)

                            addr = email or smtp or (acct_nm if "@" in acct_nm else "")
                            if not addr or addr in seen_in_profile:
                                continue
                            seen_in_profile.add(addr)

                            accounts.append({
                                "profile":      profile_name,
                                "display_name": display or acct_nm or "N/A",
                                "email":        addr,
                            })
                        except Exception:
                            pass
                    winreg.CloseKey(acct_root)
                except Exception:
                    pass
        finally:
            winreg.CloseKey(profiles_key)

        return accounts

    def _thunderbird_accounts(self):
        """
        Reads %APPDATA%\Thunderbird\profiles.ini and then each profile's
        prefs.js to extract mail.identity email addresses.
        """
        accounts   = []
        appdata    = os.environ.get("APPDATA", "")
        ini_path   = os.path.join(appdata, "Thunderbird", "profiles.ini")

        if not os.path.isfile(ini_path):
            return accounts

        # Minimal INI parser (no configparser to keep stdlib usage lean)
        profile_paths = []
        current_path  = None
        is_relative   = False
        base_dir      = os.path.dirname(ini_path)

        try:
            with open(ini_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.lower().startswith("path="):
                        current_path = line.split("=", 1)[1]
                    elif line.lower().startswith("isrelative="):
                        is_relative = line.split("=", 1)[1].strip() == "1"
                    elif line.startswith("[") and current_path:
                        full = (
                            os.path.join(base_dir, current_path)
                            if is_relative else current_path
                        )
                        profile_paths.append(full)
                        current_path = None
                        is_relative  = False
            # Flush last entry
            if current_path:
                full = (
                    os.path.join(base_dir, current_path)
                    if is_relative else current_path
                )
                profile_paths.append(full)
        except Exception:
            return accounts

        # Parse prefs.js in each profile for identity email addresses.
        # Each identity spans two separate pref lines (useremail and
        # fullName), so they're collected per identity id and merged.
        for prof_dir in profile_paths:
            prefs_path = os.path.join(prof_dir, "prefs.js")
            if not os.path.isfile(prefs_path):
                continue
            try:
                identities = {}
                with open(prefs_path, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        # Lines look like:
                        # user_pref("mail.identity.id1.useremail", "user@example.com");
                        # user_pref("mail.identity.id1.fullName", "Nome Sobrenome");
                        match = re.search(
                            r'mail\.identity\.(id\d+)\.(useremail|fullName)"\s*,\s*"([^"]*)"',
                            line,
                        )
                        if not match:
                            continue
                        ident_id, field, value = match.groups()
                        identities.setdefault(ident_id, {})[field] = value

                for ident_id in sorted(identities):
                    fields = identities[ident_id]
                    email  = fields.get("useremail")
                    if not email:
                        continue
                    accounts.append({
                        "profile":      os.path.basename(prof_dir),
                        "display_name": fields.get("fullName") or email,
                        "email":        email,
                    })
            except Exception:
                pass

        return accounts

    # ============================================================
    # RUNTIME SNAPSHOT  (instantaneous values, changes every run)
    # ============================================================
    def _collect_runtime(self):
        if not _HAS_PSUTIL:
            return {}
        try:
            cpu_pct = psutil.cpu_percent(interval=1)
            freq    = psutil.cpu_freq()
            vm      = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            net_io  = psutil.net_io_counters()

            r = {
                "cpu_usage_pct":    cpu_pct,
                "cpu_freq_mhz":     round(freq.current, 0) if freq else None,
                "ram_usage_pct":    vm.percent,
                "ram_used_gb":      round(vm.used      / (1024 ** 3), 2),
                "ram_available_gb": round(vm.available / (1024 ** 3), 2),
            }
            if disk_io:
                r["disk_read_gb"]  = round(disk_io.read_bytes  / (1024 ** 3), 2)
                r["disk_write_gb"] = round(disk_io.write_bytes / (1024 ** 3), 2)
            if net_io:
                r["net_sent_mb"]   = round(net_io.bytes_sent / (1024 ** 2), 2)
                r["net_recv_mb"]   = round(net_io.bytes_recv / (1024 ** 2), 2)
            return r
        except Exception:
            return {}

    # ============================================================
    # SERIALIZATION
    # ============================================================
    def to_json(self, data=None, indent=2):
        """Serializes collected data to a JSON string."""
        if data is None:
            data = self.collect()
        return json.dumps(data, ensure_ascii=False, indent=indent)

    def to_csv(self, data=None):
        """
        Serializes collected data to CSV.
        Nested dicts are flattened with dot notation.
        Lists of scalars are joined with semicolons.
        """
        if data is None:
            data = self.collect()
        rows   = self._flatten(data)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["key", "value"])
        for key, value in rows:
            writer.writerow([key, value])
        return output.getvalue()

    def to_html(self, data=None):
        """
        Serializes collected data to a self-contained HTML report with a
        sidebar for navigating between sections (see util.report_html).
        """
        if data is None:
            data = self.collect()
        return render_report(data)

    # ============================================================
    # PERSISTENCE
    # ============================================================
    def save(self, content, path):
        """Writes text content to a file using UTF-8 encoding."""
        dirpath = os.path.dirname(os.path.abspath(path))
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================
    def _flatten(self, obj, prefix=""):
        """Recursively flattens a nested structure to (dotted_key, value) pairs."""
        items = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    items.extend(self._flatten(v, full))
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            items.extend(self._flatten(item, f"{full}[{i}]"))
                        else:
                            items.append((f"{full}[{i}]", item))
                else:
                    items.append((full, v))
        return items

    def _reg_str(self, key, value_name):
        """Reads a string value from an open registry key. Returns '' on failure."""
        try:
            val, _ = winreg.QueryValueEx(key, value_name)
            return str(val).strip()
        except OSError:
            return ""

    def _reg_int(self, key, value_name):
        """Reads an integer value from an open registry key. Returns 0 on failure."""
        try:
            val, _ = winreg.QueryValueEx(key, value_name)
            return int(val)
        except (OSError, ValueError, TypeError):
            return 0