import threading
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

from app.app import App
from util.schemes import SchemeBuilder
from util.report_html import render_report, render_consolidated


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
    # CONVERTER JSON(s) EXISTENTE(S) PARA HTML
    # source_path: caminho de um arquivo .json ou de uma pasta
    # is_folder:   True -> gera um HTML consolidado com todos os
    #              .json da pasta; False -> converte um unico arquivo
    # ============================================================
    def convert_json_to_html(self, source_path, is_folder):
        def _run():
            self._progress_start("Convertendo JSON para HTML...")
            self.log_title("Converter JSON para HTML")
            try:
                if is_folder:
                    folder  = Path(source_path)
                    entries = []

                    for file in sorted(folder.glob("*.json")):
                        try:
                            with open(file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            entries.append((file.stem, data))
                            self.log_info(f"Lido: {file.name}")
                        except Exception as e:
                            self.log_warn(f"Ignorado {file.name}: {e}")

                    if not entries:
                        self.log_error("Nenhum JSON valido encontrado na pasta.")
                        return

                    html      = render_consolidated(entries)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    out_path  = folder / f"relatorio_consolidado_{timestamp}.html"
                    out_path.write_text(html, encoding="utf-8")
                    self.log_ok(
                        f"HTML consolidado gerado ({len(entries)} maquina(s)): {out_path}"
                    )
                else:
                    json_path = Path(source_path)
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    html      = render_report(data)
                    hostname  = data.get("system", {}).get("hostname", "relatorio")
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    out_path  = json_path.parent / f"{hostname}_{timestamp}.html"
                    out_path.write_text(html, encoding="utf-8")
                    self.log_ok(f"HTML gerado: {out_path}")

            except PermissionError:
                self.log_error(f"Permissao negada ao gravar em: {source_path}")
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