import os

from app.app import App

try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False


# Chaves Run do registro (hive, caminho, rotulo, tipo_approved)
_RUN_KEYS = []
if _HAS_WINREG:
    _RUN_KEYS = [
        (winreg.HKEY_CURRENT_USER,
         r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU", "Run"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM", "Run"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run",
         "HKLM32", "Run32"),
    ]

_APPROVED_BASE = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"

_ENABLED_BYTES  = bytes([2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
_DISABLED_BYTES = bytes([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])


class Startup(App):
    """
    Gerenciador de inicializacao do Windows.

    Lista entradas das chaves Run (HKCU/HKLM/Wow6432Node) e das pastas
    de Inicializar. Liga/desliga pelo mesmo mecanismo do Gerenciador de
    Tarefas (StartupApproved), sem apagar a entrada original -> reversivel.
    """

    def __init__(self):
        super().__init__()

    # ============================================================
    # LISTAGEM
    # ============================================================
    def startup_list(self):
        if not _HAS_WINREG:
            return []
        items = []
        for hive, path, label, approved_kind in _RUN_KEYS:
            items.extend(self._read_run_key(hive, path, label, approved_kind))
        items.extend(self._read_startup_folders())
        return items

    def _read_run_key(self, hive, path, label, approved_kind):
        out = []
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
        except FileNotFoundError:
            return out
        except OSError:
            return out
        try:
            i = 0
            while True:
                try:
                    name, value, _t = winreg.EnumValue(key, i)
                except OSError:
                    break
                i += 1
                enabled = self._is_enabled(hive, approved_kind, name)
                out.append({
                    "name": name,
                    "command": str(value),
                    "location": label,
                    "enabled": enabled,
                    "kind": "run",
                    "hive": hive,
                    "approved_kind": approved_kind,
                    "approved_name": name,
                })
        finally:
            winreg.CloseKey(key)
        return out

    def _read_startup_folders(self):
        out = []
        folders = []
        appdata = os.environ.get("APPDATA", "")
        programdata = os.environ.get("ProgramData", "")
        if appdata:
            folders.append((winreg.HKEY_CURRENT_USER, os.path.join(
                appdata, r"Microsoft\Windows\Start Menu\Programs\Startup"), "Pasta (usuario)"))
        if programdata:
            folders.append((winreg.HKEY_LOCAL_MACHINE, os.path.join(
                programdata, r"Microsoft\Windows\Start Menu\Programs\Startup"),
                "Pasta (todos)"))
        for hive, folder, label in folders:
            if not os.path.isdir(folder):
                continue
            for fn in os.listdir(folder):
                full = os.path.join(folder, fn)
                if not os.path.isfile(full):
                    continue
                enabled = self._is_enabled(hive, "StartupFolder", fn)
                out.append({
                    "name": fn,
                    "command": full,
                    "location": label,
                    "enabled": enabled,
                    "kind": "folder",
                    "hive": hive,
                    "approved_kind": "StartupFolder",
                    "approved_name": fn,
                })
        return out

    def _is_enabled(self, hive, approved_kind, name):
        """Le o estado em StartupApproved. Ausente = habilitado."""
        try:
            key = winreg.OpenKey(hive, f"{_APPROVED_BASE}\\{approved_kind}",
                                 0, winreg.KEY_READ)
        except OSError:
            return True
        try:
            data, _t = winreg.QueryValueEx(key, name)
            if data and len(data) >= 1:
                return (data[0] & 1) == 0  # impar = desabilitado
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return True
        finally:
            winreg.CloseKey(key)

    # ============================================================
    # LIGAR / DESLIGAR
    # ============================================================
    def startup_set_enabled(self, item, enabled):
        """Grava o estado em StartupApproved. Retorna (ok, mensagem)."""
        if not _HAS_WINREG:
            return False, "winreg indisponivel."
        hive = item["hive"]
        approved_kind = item["approved_kind"]
        name = item["approved_name"]
        try:
            try:
                key = winreg.OpenKey(hive, f"{_APPROVED_BASE}\\{approved_kind}",
                                     0, winreg.KEY_SET_VALUE)
            except FileNotFoundError:
                key = winreg.CreateKey(hive, f"{_APPROVED_BASE}\\{approved_kind}")
            winreg.SetValueEx(key, name, 0, winreg.REG_BINARY,
                              _ENABLED_BYTES if enabled else _DISABLED_BYTES)
            winreg.CloseKey(key)
            estado = "habilitada" if enabled else "desabilitada"
            self.log_ok(f"Inicializacao '{name}' {estado}.")
            return True, f"'{name}' {estado}."
        except PermissionError:
            return False, "Permissao negada. Execute como Administrador."
        except Exception as e:
            return False, str(e)
