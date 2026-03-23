import json
import csv
import io
import os
import sys
import platform
import socket
import getpass
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
SCHEMA_VERSION = "0.2"

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
                  gpu, network, audio, software, runtime.
        """
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "system":         self._collect_system(),
            "bios":           self._collect_bios(),
            "motherboard":    self._collect_motherboard(),
            "cpu":            self._collect_cpu(),
            "memory":         self._collect_memory(),
            "storage":        self._collect_storage(),
            "gpu":            self._collect_gpu(),
            "network":        self._collect_network(),
            "audio":          self._collect_audio(),
            "software":       self._collect_software(),
            "runtime":        self._collect_runtime(),
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

        # OS install date, serial and build number via WMI
        if _HAS_WMI:
            try:
                pythoncom.CoInitialize()
                c = wmi.WMI()
                for os_obj in c.Win32_OperatingSystem():
                    raw = str(os_obj.InstallDate or "")
                    if len(raw) >= 8:
                        d["os_install_date"]  = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
                    d["os_serial"]            = str(os_obj.SerialNumber    or "N/A")
                    d["os_build"]             = str(os_obj.BuildNumber     or "N/A")
                    d["os_registered_to"]     = str(os_obj.RegisteredUser  or "N/A")
                    break
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        return d

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
                    d["socket"]          = str(cpu.SocketDesignation or "N/A")
                    d["manufacturer"]    = str(cpu.Manufacturer      or "N/A")
                    d["max_clock_mhz"]   = str(cpu.MaxClockSpeed     or "N/A")
                    d["l2_cache_kb"]     = str(cpu.L2CacheSize       or "N/A")
                    d["l3_cache_kb"]     = str(cpu.L3CacheSize       or "N/A")
                    d["processor_id"]    = str(cpu.ProcessorId       or "N/A").strip()
                    d["virtualization"]  = (
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
                        "model":             str(disk.Model             or "N/A"),
                        "interface":         str(disk.InterfaceType     or "N/A"),
                        "media_type":        str(disk.MediaType         or "N/A"),
                        "size_gb":           round(int(disk.Size or 0) / (1024 ** 3), 2),
                        "partitions":        int(disk.Partitions        or 0),
                        "serial_number":     str(disk.SerialNumber      or "N/A").strip(),
                        "firmware":          str(disk.FirmwareRevision  or "N/A"),
                        "bytes_per_sector":  int(disk.BytesPerSector    or 0),
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
                        "ip_addresses":    list(nic.IPAddress             or []),
                        "subnets":         list(nic.IPSubnet              or []),
                        "default_gateway": list(nic.DefaultIPGateway      or []),
                        "dns_servers":     list(nic.DNSServerSearchOrder  or []),
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
                    "bytes_sent_mb":  round(net.bytes_sent / (1024 ** 2), 2),
                    "bytes_recv_mb":  round(net.bytes_recv / (1024 ** 2), 2),
                    "packets_sent":   net.packets_sent,
                    "packets_recv":   net.packets_recv,
                    "errors_out":     net.errout,
                    "errors_in":      net.errin,
                }
            except Exception:
                pass

        return {"adapters": adapters, "counters": counters}

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
                    "name":          str(dev.Name         or "N/A"),
                    "manufacturer":  str(dev.Manufacturer or "N/A"),
                    "status":        str(dev.Status       or "N/A"),
                    "pnp_device_id": str(dev.PNPDeviceID  or "N/A"),
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
    # SOFTWARE
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

        skip_keys    = {"schema_version", "generated_at"}
        sections_html = ""

        for section_key, section_val in data.items():
            if section_key in skip_keys:
                continue

            title = section_key.upper().replace("_", " ")
            block = ""

            if isinstance(section_val, list):
                block = self._html_cards(section_val)
            elif isinstance(section_val, dict):
                # Separate scalar pairs from sub-lists
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
            html += (
                f"<div class='card'><table>{rows}</table></div>"
            )
        return html