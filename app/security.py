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

    # ============================================================
    # EDITOR DO ARQUIVO HOSTS
    # Leitura/gravacao direta. A gravacao exige privilegio de admin
    # (o app ja roda elevado). Faz backup antes de sobrescrever.
    # ============================================================
    HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"

    def hosts_read(self):
        """Retorna (ok, conteudo_ou_erro)."""
        try:
            with open(self.HOSTS_PATH, "r", encoding="utf-8", errors="replace") as f:
                return True, f.read()
        except Exception as e:
            return False, str(e)

    def hosts_save(self, content):
        """Grava o hosts (com backup .bak). Retorna (ok, mensagem)."""
        try:
            # Backup com data/hora
            try:
                import shutil
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(self.HOSTS_PATH, f"{self.HOSTS_PATH}.{ts}.bak")
            except Exception:
                pass
            with open(self.HOSTS_PATH, "w", encoding="utf-8", errors="replace") as f:
                f.write(content)
            self.log_ok("Arquivo HOSTS salvo (backup .bak criado).")
            return True, "HOSTS salvo (backup criado)."
        except PermissionError:
            return False, "Permissao negada. Execute como Administrador."
        except Exception as e:
            return False, str(e)

    def hosts_block(self, domain):
        """Acrescenta uma linha de bloqueio para o dominio. Retorna (ok, mensagem)."""
        domain = (domain or "").strip().lower()
        domain = domain.replace("http://", "").replace("https://", "").strip("/")
        if not domain or " " in domain:
            return False, "Dominio invalido."
        ok, content = self.hosts_read()
        if not ok:
            return False, content
        if domain in content:
            return False, f"'{domain}' ja aparece no HOSTS."
        novo = content.rstrip() + f"\n0.0.0.0 {domain}\n0.0.0.0 www.{domain}\n"
        return self.hosts_save(novo)

    # ============================================================
    # CHAVE DE PRODUTO DO WINDOWS
    # Duas fontes:
    #   1) Chave OEM embutida no firmware (UEFI/BIOS) via WMI.
    #   2) Chave instalada, decodificada de HKLM ...\DigitalProductId.
    # Util para recuperar a licenca da propria maquina.
    # ============================================================
    def check_windows_key(self):
        self.log_title("Chave de Produto do Windows")
        self._progress_start("Lendo chave de produto...")
        try:
            oem = self._get_oem_key()
            if oem:
                self.log_info(f"Chave OEM (firmware)   : {oem}")
            else:
                self.log_info("Chave OEM (firmware)   : nao encontrada "
                              "(maquina sem chave OEM no UEFI/BIOS).")

            inst = self._get_installed_key()
            if inst:
                self.log_info(f"Chave instalada (reg.) : {inst}")
            else:
                self.log_info("Chave instalada (reg.) : nao foi possivel decodificar.")

            self.log("")
            self.log_warn("A chave OEM nem sempre coincide com a chave instalada "
                          "(ex.: Windows atualizado ou licenca digital/conta MS).")
        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Concluido.")
            self.log("")

    def _get_oem_key(self):
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 '(Get-CimInstance -ClassName SoftwareLicensingService)'
                 '.OA3xOriginalProductKey'],
                capture_output=True, timeout=20,
            )
            return self._decode(result.stdout).strip() or None
        except Exception:
            return None

    def _get_installed_key(self):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
            try:
                data, _t = winreg.QueryValueEx(key, "DigitalProductId")
            finally:
                winreg.CloseKey(key)
            return self._decode_product_key(bytes(data))
        except Exception:
            return None

    @staticmethod
    def _decode_product_key(digital_product_id):
        """Decodifica a chave de produto (compativel com Win7 e Win8/10/11)."""
        digits = "BCDFGHJKMPQRTVWXY2346789"
        dpid = bytearray(digital_product_id)
        if len(dpid) < 67:
            return None
        is_win8 = (dpid[66] // 6) & 1
        dpid[66] = (dpid[66] & 0xF7) | ((is_win8 & 2) * 4)

        pkey = ""
        current = 0
        for _i in range(24, -1, -1):
            current = 0
            for j in range(14, -1, -1):
                current = current * 256 + dpid[j + 52]
                dpid[j + 52] = current // 24
                current = current % 24
            pkey = digits[current] + pkey

        if is_win8 == 1:
            keypart1 = pkey[1:current + 1]
            keypart2 = pkey[current + 1:]
            pkey = keypart1 + "N" + keypart2

        pkey = pkey[:25]
        return "-".join(pkey[i:i + 5] for i in range(0, 25, 5))

    def check_bitlocker_status(self):
        self.run_command("Status do BitLocker", COMMANDS["check_bitlocker_status"])

    def check_firewall_status(self):
        self.run_command("Status do Firewall", COMMANDS["check_firewall_status"])

    def check_tpm_secureboot(self):
        self.run_command("TPM / Secure Boot", COMMANDS["check_tpm_secureboot"])