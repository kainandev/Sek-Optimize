from config import *
from app.app import App


class Network(App):
    """Ferramentas de rede e diagnostico de conectividade."""

    def __init__(self):
        super().__init__()

    def flush_dns(self):
        self.run_command("Limpando DNS", COMMANDS["flush_dns"])

    def reset_network(self):
        self.run_command("Resetando configuracoes de rede", COMMANDS["reset_network"])

    def reset_winsock(self):
        self.run_command("Resetando Winsock", COMMANDS["reset_winsock"])

    def run_ipconfig(self):
        self.run_command("IPConfig", COMMANDS["run_ipconfig"])

    def ping_google(self):
        self.run_command("Ping Google", COMMANDS["ping_google"])

    def run_tracert(self):
        self.run_command("Traceroute Google", COMMANDS["run_tracert"])

    def run_nslookup(self):
        self.run_command("NSLookup Google", COMMANDS["run_nslookup"])

    def show_active_connections(self):
        self.run_command("Conexoes ativas (ESTABLISHED)", COMMANDS["show_active_connections"])

    def renew_ip(self):
        self.log_warn("A conexao de rede sera interrompida brevemente.")
        self.run_command("Renovando IP (release + renew)", COMMANDS["renew_ip"])

    def show_open_ports(self):
        self.run_command("Portas em escuta (LISTENING)", COMMANDS["show_open_ports"])

    def list_services_running(self):
        self.run_command("Servicos em execucao", COMMANDS["list_services_running"])

    def run_netstat(self):
        self.run_command("Netstat", "netstat -ano")

    def run_arp(self):
        self.run_command("Tabela ARP", "arp -a")

    def run_route(self):
        self.run_command("Tabela de Rotas", "route print")

    # ============================================================
    # TESTE DE VELOCIDADE REAL (download + upload)
    # Usa o backend publico da Cloudflare (speed.cloudflare.com), sem
    # necessidade de chave/API - o mesmo usado pelo site oficial deles.
    # ============================================================
    def speed_test(self):
        self.log_title("Teste de Velocidade Real (Download/Upload)")
        self._progress_start("Testando velocidade de internet...")
        try:
            import urllib.request

            # Cloudflare bloqueia como bot requisicoes sem User-Agent de navegador.
            ua_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SekOptimize/SpeedTest"
                )
            }

            down_url = "https://speed.cloudflare.com/__down?bytes=25000000"
            self.log_info("Testando download (~25 MB)...")
            t0  = time.time()
            req = urllib.request.Request(down_url, headers=ua_headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                total = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
            elapsed = time.time() - t0
            down_mbps = (total * 8 / 1_000_000) / elapsed if elapsed > 0 else 0
            self.log(
                f"  Download      : {down_mbps:.2f} Mbps  "
                f"({total / (1024 ** 2):.1f} MB em {elapsed:.2f}s)"
            )

            up_url  = "https://speed.cloudflare.com/__up"
            payload = os.urandom(5_000_000)
            self.log_info("Testando upload (~5 MB)...")
            t0  = time.time()
            req = urllib.request.Request(up_url, data=payload, method="POST", headers=ua_headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
            elapsed  = time.time() - t0
            up_mbps  = (len(payload) * 8 / 1_000_000) / elapsed if elapsed > 0 else 0
            self.log(
                f"  Upload        : {up_mbps:.2f} Mbps  "
                f"({len(payload) / (1024 ** 2):.1f} MB em {elapsed:.2f}s)"
            )

        except Exception as e:
            self.log_error(f"Falha no teste de velocidade (verifique a conexao): {e}")
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Teste concluido.")
            self.log("")

    # ============================================================
    # REDES WI-FI SALVAS E SENHAS
    # Parsing independente de idioma: qualquer linha "rotulo : valor"
    # no output do netsh e candidata (funciona tanto em PT-BR quanto
    # EN-US, ja que nao depende do texto exato do rotulo).
    # ============================================================
    def list_wifi_passwords(self):
        self.log_title("Redes Wi-Fi Salvas e Senhas")
        self._progress_start("Consultando perfis Wi-Fi...")
        try:
            profiles_out = self._run_netsh(["wlan", "show", "profiles"])
            names = []
            for line in profiles_out.splitlines():
                if ":" not in line:
                    continue
                name = line.split(":", 1)[1].strip()
                if name and name not in names:
                    names.append(name)

            if not names:
                self.log_warn(
                    "Nenhum perfil Wi-Fi salvo encontrado "
                    "(ou este PC nao tem adaptador Wi-Fi)."
                )

            key_labels = ("key content", "conteudo da chave", "conteúdo da chave")
            for name in names:
                detail = self._run_netsh(
                    ["wlan", "show", "profile", f"name={name}", "key=clear"]
                )
                senha = "N/A (rede aberta ou nao foi possivel ler)"
                for line in detail.splitlines():
                    if ":" not in line:
                        continue
                    label = line.split(":", 1)[0].strip().lower()
                    if label in key_labels:
                        senha = line.split(":", 1)[1].strip()
                        break

                self.log(f"[{name}]")
                self.log(f"  Senha : {senha}")
                self.log("")

        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Consulta concluida.")
            self.log("")

    def _run_netsh(self, args):
        result = subprocess.run(["netsh"] + args, capture_output=True, timeout=15)
        return self._decode(result.stdout)