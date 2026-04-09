import json
import csv
import io
import os
import sys
import platform
import socket
import getpass
import subprocess
import winreg
from datetime import datetime

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


# Version bumped when new top-level keys are added to the schema.
SCHEMA_VERSION = "0.3"

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
        Sections: system, bios, motherboard, cpu, memory, storage, gpu,
                  network, open_ports, audio, software, installed_programs,
                  startup_programs, local_users, antivirus, email_clients,
                  runtime.
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

    def _outlook_accounts_from_registry(self, hive, profiles_path):
        """
        Walks HKCU\...\Profiles\<profile>\9375CFF0... to extract
        account display names and email addresses stored by Outlook.
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
                    acct_key_path = f"{profiles_path}\\{profile_name}\\{_ACCOUNT_SUBKEY}"
                    acct_root     = winreg.OpenKey(hive, acct_key_path)
                    j = 0
                    while True:
                        try:
                            acct_sub = winreg.EnumKey(acct_root, j)
                            j += 1
                        except OSError:
                            break
                        try:
                            sub = winreg.OpenKey(acct_root, acct_sub)
                            display = self._reg_str(sub, "Display Name")
                            email   = self._reg_str(sub, "Email")
                            smtp    = self._reg_str(sub, "SMTP Email Address")
                            addr    = email or smtp or ""
                            winreg.CloseKey(sub)
                            if display or addr:
                                accounts.append({
                                    "profile":      profile_name,
                                    "display_name": display or "N/A",
                                    "email":        addr     or "N/A",
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

        # Parse prefs.js in each profile for identity email addresses
        for prof_dir in profile_paths:
            prefs_path = os.path.join(prof_dir, "prefs.js")
            if not os.path.isfile(prefs_path):
                continue
            try:
                with open(prefs_path, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        # Lines look like:
                        # user_pref("mail.identity.id1.useremail", "user@example.com");
                        if "useremail" in line and "user_pref" in line:
                            parts = line.split('"')
                            if len(parts) >= 4:
                                key   = parts[1]
                                value = parts[3]
                                accounts.append({
                                    "profile":      os.path.basename(prof_dir),
                                    "display_name": key,
                                    "email":        value,
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
        """Serializes collected data to a self-contained HTML document."""
        if data is None:
            data = self.collect()

        hostname  = data.get("system", {}).get("hostname", "N/A")
        generated = data.get("generated_at", "")
        schema_v  = data.get("schema_version", "N/A")

        skip_keys     = {"schema_version", "generated_at"}
        sections_html = ""

        for section_key, section_val in data.items():
            if section_key in skip_keys:
                continue

            title = section_key.upper().replace("_", " ")
            block = ""

            if isinstance(section_val, list):
                # Flat list of dicts (gpu, audio, open_ports, etc.)
                block = self._html_cards(section_val)
            elif isinstance(section_val, dict):
                scalar_pairs = [
                    (k, v) for k, v in section_val.items()
                    if not isinstance(v, list)
                ]
                list_pairs = [
                    (k, v) for k, v in section_val.items()
                    if isinstance(v, list)
                ]
                if scalar_pairs:
                    block += self._html_kv_table(scalar_pairs)
                for sub_key, sub_list in list_pairs:
                    sub_title = sub_key.replace("_", " ").title()
                    block += (
                        f"<p class='sub-title'>{sub_title}</p>"
                        + self._html_cards(sub_list)
                    )
            else:
                block = self._html_kv_table([(section_key, section_val)])

            sections_html += (
                f"<div class='section'><h2>{title}</h2>{block}</div>\n"
            )

        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            f"  <title>System Report - {hostname}</title>\n"
            "  <style>\n"
            "    *{box-sizing:border-box;margin:0;padding:0}\n"
            "    body{font-family:'Segoe UI',Arial,sans-serif;"
            "background:#18181f;color:#d8d8e8;padding:28px}\n"
            "    h1{color:#4a80ff;font-size:1.5em;margin-bottom:4px}\n"
            "    p.meta{color:#6868a0;font-size:.83em;margin-bottom:24px}\n"
            "    .section{margin-bottom:26px}\n"
            "    h2{color:#4a80ff;font-size:.92em;text-transform:uppercase;"
            "letter-spacing:.08em;border-bottom:1px solid #2e2e3e;"
            "padding-bottom:5px;margin-bottom:10px}\n"
            "    p.sub-title{color:#6868a0;font-size:.8em;margin:10px 0 4px}\n"
            "    table{border-collapse:collapse;width:100%;max-width:900px;"
            "margin-bottom:8px}\n"
            "    th,td{padding:5px 14px;text-align:left;"
            "border-bottom:1px solid #22222e;font-size:.85em}\n"
            "    th{background:#22222e;color:#4a80ff;font-weight:600}\n"
            "    tr:hover td{background:#22222e}\n"
            "    .card{background:#1c1c28;border:1px solid #2e2e3e;"
            "border-radius:4px;padding:10px 14px;margin-bottom:8px;"
            "max-width:900px}\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <h1>System Report</h1>\n"
            f"  <p class='meta'>"
            f"Host: <strong>{hostname}</strong>&nbsp;&nbsp;"
            f"Generated: {generated}&nbsp;&nbsp;"
            f"Schema: v{schema_v}</p>\n"
            f"{sections_html}"
            "</body>\n"
            "</html>"
        )

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

    def _html_kv_table(self, pairs):
        """Renders key/value pairs as a two-column HTML table."""
        if not pairs:
            return ""
        rows = ""
        for k, v in pairs:
            label = str(k).replace("_", " ").title()
            if isinstance(v, list):
                v = "; ".join(str(x) for x in v)
            rows += f"<tr><td><strong>{label}</strong></td><td>{v}</td></tr>\n"
        return (
            "<table>"
            "<tr><th>Property</th><th>Value</th></tr>"
            f"{rows}"
            "</table>"
        )

    def _html_cards(self, items):
        """Renders a list of dicts as stacked cards (one card per item)."""
        if not items:
            return "<p style='color:#6868a0;font-size:.83em'>No data.</p>"
        html = ""
        for item in items:
            if not isinstance(item, dict):
                continue
            rows = ""
            for k, v in item.items():
                label = str(k).replace("_", " ").title()
                if isinstance(v, list):
                    v = "; ".join(str(x) for x in v)
                rows += (
                    f"<tr><td><strong>{label}</strong></td>"
                    f"<td>{v}</td></tr>\n"
                )
            html += f"<div class='card'><table>{rows}</table></div>"
        return html

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