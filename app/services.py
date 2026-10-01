import subprocess

from app.app import App

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


class Services(App):
    """
    Gerenciador de servicos do Windows.

    Lista via psutil e controla via 'sc' (start/stop/config). As acoes de
    parar/desabilitar exigem privilegio de administrador (o app roda elevado).
    """

    def __init__(self):
        super().__init__()

    # ============================================================
    # LISTAGEM
    # ============================================================
    def services_list(self):
        if not _HAS_PSUTIL:
            return []
        out = []
        for s in psutil.win_service_iter():
            try:
                info = s.as_dict()
                out.append({
                    "name": info.get("name", ""),
                    "display": info.get("display_name", ""),
                    "status": info.get("status", ""),
                    "start": info.get("start_type", ""),
                })
            except Exception:
                continue
        out.sort(key=lambda d: (d["display"] or d["name"]).lower())
        return out

    # ============================================================
    # CONTROLE
    # ============================================================
    def _run_sc(self, args, desc):
        try:
            self.log_title(desc)
            result = subprocess.run(
                ["sc"] + args, capture_output=True, timeout=20)
            out = self._decode(result.stdout) + self._decode(result.stderr)
            for line in out.splitlines():
                if line.strip():
                    self.log(line.rstrip())
            ok = result.returncode == 0
            if ok:
                self.log_ok("Comando executado.")
            else:
                self.log_warn(f"Codigo de retorno: {result.returncode}")
            return ok, ("OK." if ok else f"Falha (codigo {result.returncode}).")
        except Exception as e:
            self.log_error(str(e))
            return False, str(e)

    def service_start(self, name):
        return self._run_sc(["start", name], f"Iniciar servico {name}")

    def service_stop(self, name):
        return self._run_sc(["stop", name], f"Parar servico {name}")

    def service_set_start(self, name, mode):
        """mode: 'auto' | 'demand' (manual) | 'disabled'."""
        valid = {"auto": "auto", "demand": "demand", "manual": "demand",
                 "disabled": "disabled"}
        m = valid.get(mode, "demand")
        return self._run_sc(["config", name, "start=", m],
                            f"Tipo de inicio de {name} -> {m}")
