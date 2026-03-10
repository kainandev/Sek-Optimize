from config import *
from app.app import App


class Security(App):
    """Seguranca, privacidade e analise do ambiente."""

    def __init__(self):
        super().__init__()

    # ============================================================
    # EXIBIR ARQUIVO HOSTS
    # Leitura direta via Python; nao precisa de shell.
    # ============================================================
    def show_hosts_file(self):
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        self.log_title("Arquivo HOSTS")
        self._progress_start("Lendo hosts...")

        try:
            with open(hosts_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total = 0
            for line in lines:
                stripped = line.rstrip()
                self.log(stripped)
                if stripped and not stripped.startswith("#"):
                    total += 1

            self.log("")
            self.log_info(f"Total de entradas ativas (sem comentarios): {total}")

        except PermissionError:
            self.log_error("Permissao negada. Execute como Administrador.")
        except FileNotFoundError:
            self.log_error(f"Arquivo nao encontrado: {hosts_path}")
        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Leitura concluida.")
            self.log("")

    # ============================================================
    # TESTE DE VELOCIDADE DNS
    # Compara tempo de resolucao entre multiplos servidores DNS.
    # Usa subprocess nslookup pois nao requer bibliotecas externas.
    # ============================================================
    def test_dns_speed(self):
        self.log_title("Teste de Velocidade DNS")
        self._progress_start("Testando servidores DNS...")

        servidores = {
            "Google      (8.8.8.8)":          "8.8.8.8",
            "Cloudflare  (1.1.1.1)":          "1.1.1.1",
            "OpenDNS     (208.67.222.222)":   "208.67.222.222",
            "Quad9       (9.9.9.9)":           "9.9.9.9",
        }
        host_teste = "www.google.com"

        self.log(f"  Host de teste : {host_teste}")
        self.log(f"  {'Servidor':<32}  {'Tempo':>8}  Resultado")
        self.log(f"  {'-'*32}  {'-'*8}  {'-'*20}")

        try:
            import subprocess as sp
            for nome, dns in servidores.items():
                t0 = time.time()
                try:
                    result = sp.run(
                        ["nslookup", host_teste, dns],
                        capture_output=True,
                        timeout=5,
                    )
                    elapsed = (time.time() - t0) * 1000
                    ok = result.returncode == 0
                    status = "[OK]" if ok else "[FALHA]"
                    self.log(f"  {nome:<32}  {elapsed:>6.0f}ms  {status}")
                except Exception as e:
                    self.log(f"  {nome:<32}  {'ERRO':>8}  {e}")

        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Teste concluido.")
            self.log("")

    # ============================================================
    # EXPORT CONFIGURACAO DE REDE PARA ARQUIVO
    # ============================================================
    def export_network_config(self):
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"network_config_{ts}.txt"

        self.log_title("Exportar Configuracao de Rede")
        self._progress_start("Exportando...")

        try:
            import subprocess as sp
            result = sp.run(
                "ipconfig /all",
                shell=True,
                capture_output=True,
            )
            raw = result.stdout
            # Tenta utf-8, depois cp850
            for enc in ("utf-8", "cp850", "latin-1"):
                try:
                    content = raw.decode(enc, errors="strict")
                    break
                except UnicodeDecodeError:
                    pass
            else:
                content = raw.decode("latin-1", errors="replace")

            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            self.log_ok(f"Salvo em: {os.path.abspath(filename)}")
            # Exibe no log tambem
            for line in content.splitlines():
                self.log(line)

        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Exportacao concluida.")
            self.log("")