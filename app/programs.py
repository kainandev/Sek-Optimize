import subprocess

from app.app import App

try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

_UNINSTALL_KEYS = []
if _HAS_WINREG:
    _UNINSTALL_KEYS = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,
         r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]


class Programs(App):
    """Lista e desinstala programas usando o registro do Windows."""

    def __init__(self):
        super().__init__()

    # ============================================================
    # LISTAGEM
    # ============================================================
    def programs_list(self):
        if not _HAS_WINREG:
            return []
        seen = set()
        out = []
        for hive, path in _UNINSTALL_KEYS:
            try:
                base = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            except OSError:
                continue
            try:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(base, i)
                    except OSError:
                        break
                    i += 1
                    info = self._read_entry(hive, path, sub)
                    if info and info["name"] not in seen:
                        seen.add(info["name"])
                        out.append(info)
            finally:
                winreg.CloseKey(base)
        out.sort(key=lambda d: d["name"].lower())
        return out

    def _read_entry(self, hive, path, sub):
        try:
            key = winreg.OpenKey(hive, f"{path}\\{sub}", 0, winreg.KEY_READ)
        except OSError:
            return None
        try:
            def val(name):
                try:
                    return str(winreg.QueryValueEx(key, name)[0])
                except OSError:
                    return ""

            name = val("DisplayName")
            if not name:
                return None
            # Ignora atualizacoes/patches do sistema
            if val("SystemComponent") == "1":
                return None
            uninstall = val("QuietUninstallString") or val("UninstallString")
            return {
                "name": name,
                "version": val("DisplayVersion"),
                "publisher": val("Publisher"),
                "uninstall": uninstall,
            }
        finally:
            winreg.CloseKey(key)

    # ============================================================
    # DESINSTALACAO
    # ============================================================
    def program_uninstall(self, entry):
        """Executa o UninstallString do programa. Retorna (ok, mensagem)."""
        cmd = entry.get("uninstall", "").strip()
        if not cmd:
            return False, "Este programa nao informou comando de desinstalacao."
        try:
            self.log_title("Desinstalar Programa")
            self.log_info(f"Programa: {entry.get('name','')}")
            self.log_info(f"Comando : {cmd}")
            subprocess.Popen(cmd, shell=True)
            self.log_ok("Desinstalador iniciado (siga a janela que abriu).")
            return True, "Desinstalador iniciado."
        except Exception as e:
            self.log_error(str(e))
            return False, str(e)
