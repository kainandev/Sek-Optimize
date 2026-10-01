import json
import threading
import urllib.request
import urllib.error

from app.app import App
from config import VERSION_SOFTWARE

# Repositorio de releases no GitHub
_GITHUB_API = "https://api.github.com/repos/kainandev/Sek-Optimize/releases/latest"


def _parse_version(tag):
    """Converte 'v1.2.3' ou '1.2.3' em tupla (1,2,3) para comparacao."""
    nums = []
    for part in str(tag).lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    return tuple(nums) or (0,)


class Updates(App):
    """Verificacao de novas versoes via GitHub Releases."""

    def __init__(self):
        super().__init__()

    def check_updates(self, silent=False):
        """
        Consulta a ultima release no GitHub e compara com a versao atual.
        silent=True evita ruido quando ja esta atualizado (uso no startup).
        """
        threading.Thread(
            target=self._check_updates_run,
            args=(silent,),
            daemon=True,
        ).start()

    def _check_updates_run(self, silent):
        if not silent:
            self.log_title("Verificar Atualizacoes")
            self._progress_start("Consultando GitHub...")
        try:
            req = urllib.request.Request(
                _GITHUB_API,
                headers={"User-Agent": "SekOptimize-UpdateCheck",
                         "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))

            tag = data.get("tag_name") or data.get("name") or ""
            url = data.get("html_url", "")
            if not tag:
                if not silent:
                    self.log_warn("Nenhuma release encontrada no repositorio.")
                return

            atual = _parse_version(VERSION_SOFTWARE)
            remota = _parse_version(tag)

            if remota > atual:
                self.log_warn(f"Nova versao disponivel: {tag} "
                              f"(voce tem {VERSION_SOFTWARE}).")
                if url:
                    self.log_info(f"Baixe em: {url}")
            else:
                if not silent:
                    self.log_ok(f"Voce esta na versao mais recente "
                                f"({VERSION_SOFTWARE}).")

        except urllib.error.HTTPError as e:
            if not silent:
                if e.code == 404:
                    self.log_warn("Repositorio sem releases publicadas ainda.")
                else:
                    self.log_error(f"HTTP {e.code} ao consultar atualizacoes.")
        except urllib.error.URLError as e:
            if not silent:
                self.log_error(f"Sem conexao para verificar atualizacoes: {e.reason}")
        except Exception as e:
            if not silent:
                self.log_error(str(e))
        finally:
            if not silent:
                self._progress_stop()
                self.log_sep()
                self.log("")
