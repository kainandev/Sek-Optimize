import threading
import json
import urllib.request
import urllib.error

from app.app import App
from util.schemes import SchemeBuilder


class Reports(App):
    """Geracao e envio de relatorios do sistema."""

    def __init__(self):
        super().__init__()

    # ============================================================
    # EXPORTAR PARA ARQUIVO
    # fmt: "json" | "csv" | "html"
    # ============================================================
    def export_report(self, fmt, path):
        def _run():
            self._progress_start("Gerando relatorio...")
            self.log_title(f"Exportar Relatorio ({fmt.upper()})")
            try:
                builder = SchemeBuilder()
                data    = builder.collect()

                if fmt == "json":
                    content = builder.to_json(data)
                elif fmt == "csv":
                    content = builder.to_csv(data)
                elif fmt == "html":
                    content = builder.to_html(data)
                else:
                    self.log_error(f"Formato nao reconhecido: {fmt}")
                    return

                builder.save(content, path)
                self.log_ok(f"Relatorio salvo em: {path}")

            except PermissionError:
                self.log_error(f"Permissao negada ao gravar: {path}")
            except Exception as e:
                self.log_error(str(e))
            finally:
                self._progress_stop()
                self.log_sep()
                self.log("")

        threading.Thread(target=_run, daemon=True).start()

    # ============================================================
    # ENVIAR PARA API (POST/PUT/PATCH com payload JSON)
    #
    # Cabecalhos enviados:
    #   Content-Type  : application/json; charset=utf-8
    #   Authorization : Bearer <chave>
    #   X-API-Key     : <chave>
    #
    # O codigo de resposta HTTP e exibido no log do aplicativo.
    # ============================================================
    def send_report_api(self, url: str, key: str, method: str = "POST") -> None:
        """
        Envia o relatório para a API em uma thread separada.
        """
        def _run() -> None:
            self._progress_start("Enviando relatório...")

            self.log_title(f"Enviar Relatório para API ({method})")
            self.log_info(f"URL    : {url}")
            self.log_info(f"Método : {method}")

            try:
                # Coleta os dados
                builder = SchemeBuilder()
                data = builder.collect()

                payload = json.dumps(data, ensure_ascii=False, indent=None)

                # Prepara a requisição
                req = urllib.request.Request(
                    url=url,
                    data=payload.encode("utf-8"),
                    method=method,
                )

                req.add_header("Content-Type", "application/json; charset=utf-8")
                req.add_header("Authorization", f"Bearer {key}")
                req.add_header("X-API-Key", key)

                # Executa a requisição
                with urllib.request.urlopen(req, timeout=15) as response:
                    status_code = response.getcode()
                    body = response.read().decode("utf-8", errors="replace")

                self.log_ok(f"Resposta HTTP: {status_code}")

                if body.strip():
                    self.log_info("Corpo da resposta:")
                    for line in body.splitlines():
                        self.log(f"  {line}")

            except urllib.error.HTTPError as e:
                self._handle_http_error(e)

            except urllib.error.URLError as e:
                self.log_error(f"Erro de conexão: {e.reason}")

            except Exception as e:
                self.log_error(f"Erro inesperado: {e}")

            finally:
                self._progress_stop()
                self.log_sep()
                self.log("")

        # Inicia em thread (daemon)
        threading.Thread(target=_run, daemon=True).start()


        def _handle_http_error(self, e: urllib.error.HTTPError) -> None:
            """Método auxiliar para tratar erros HTTP de forma limpa."""
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            self.log_error(f"HTTP {e.code} - {e.reason}")

            if body.strip():
                self.log_info("Corpo da resposta:")
                for line in body.splitlines():
                    self.log(f"  {line}")