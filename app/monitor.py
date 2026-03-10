from config import *
from app.app import App


class Monitor(App):
    """Monitoramento de recursos do sistema via psutil."""

    def __init__(self):
        super().__init__()

    # ============================================================
    # SNAPSHOT DO SISTEMA
    # ============================================================
    def system_snapshot(self):
        self.log_title("Snapshot do Sistema")
        self._progress_start("Coletando dados do sistema...")

        try:
            # CPU
            cpu_pct  = psutil.cpu_percent(interval=1)
            cpu_freq = psutil.cpu_freq()
            cpu_cores = psutil.cpu_count(logical=False)
            cpu_threads = psutil.cpu_count(logical=True)
            freq_str = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/D"

            self.log("[CPU]")
            self.log(f"  Uso atual     : {cpu_pct}%")
            self.log(f"  Frequencia    : {freq_str}")
            self.log(f"  Nucleos       : {cpu_cores} fisicos / {cpu_threads} logicos")

            # RAM
            ram = psutil.virtual_memory()
            swap = psutil.swap_memory()
            self.log("")
            self.log("[MEMORIA RAM]")
            self.log(f"  Total         : {ram.total  / (1024**3):.2f} GB")
            self.log(f"  Em uso        : {ram.used   / (1024**3):.2f} GB ({ram.percent}%)")
            self.log(f"  Disponivel    : {ram.available / (1024**3):.2f} GB")
            self.log(f"  Swap total    : {swap.total / (1024**3):.2f} GB")
            self.log(f"  Swap em uso   : {swap.used  / (1024**3):.2f} GB ({swap.percent}%)")

            # Disco
            disk = psutil.disk_usage("C:/")
            io   = psutil.disk_io_counters()
            self.log("")
            self.log("[DISCO C:]")
            self.log(f"  Total         : {disk.total / (1024**3):.2f} GB")
            self.log(f"  Em uso        : {disk.used  / (1024**3):.2f} GB ({disk.percent}%)")
            self.log(f"  Livre         : {disk.free  / (1024**3):.2f} GB")
            if io:
                self.log(f"  Leitura total : {io.read_bytes  / (1024**3):.2f} GB")
                self.log(f"  Escrita total : {io.write_bytes / (1024**3):.2f} GB")

            # Rede
            net = psutil.net_io_counters()
            self.log("")
            self.log("[REDE]")
            self.log(f"  Enviado       : {net.bytes_sent / (1024**2):.2f} MB")
            self.log(f"  Recebido      : {net.bytes_recv / (1024**2):.2f} MB")
            self.log(f"  Pacotes env.  : {net.packets_sent}")
            self.log(f"  Pacotes rec.  : {net.packets_recv}")
            self.log(f"  Erros env.    : {net.errout}")
            self.log(f"  Erros rec.    : {net.errin}")

            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime    = datetime.now() - boot_time
            h, rem    = divmod(int(uptime.total_seconds()), 3600)
            m, s      = divmod(rem, 60)
            self.log("")
            self.log("[SISTEMA]")
            self.log(f"  Uptime        : {h:02d}h {m:02d}m {s:02d}s")
            self.log(f"  Boot em       : {boot_time.strftime('%d/%m/%Y %H:%M:%S')}")
            self.log(f"  Processos     : {len(psutil.pids())}")

        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Snapshot concluido.")
            self.log("")

    # ============================================================
    # TOP PROCESSOS POR CPU
    # ============================================================
    def top_processes_cpu(self):
        self.log_title("Top 10 Processos por CPU")
        self._progress_start("Analisando processos...")

        try:
            # Primeira passagem para inicializar o contador de CPU
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
                try:
                    p.cpu_percent(interval=None)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            time.sleep(1)

            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
                try:
                    cpu  = p.cpu_percent(interval=None)
                    ram  = p.memory_info().rss / (1024 ** 2)
                    procs.append((cpu, p.pid, p.name(), ram))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            procs.sort(reverse=True)

            self.log(f"  {'PID':<8} {'CPU%':>6}  {'RAM(MB)':>9}  Nome")
            self.log(f"  {'-'*8} {'-'*6}  {'-'*9}  {'-'*30}")

            for cpu, pid, name, ram in procs[:10]:
                self.log(f"  {pid:<8} {cpu:>6.1f}%  {ram:>8.1f}MB  {name}")

        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Analise concluida.")
            self.log("")

    # ============================================================
    # TOP PROCESSOS POR RAM
    # ============================================================
    def top_processes_ram(self):
        self.log_title("Top 10 Processos por RAM")
        self._progress_start("Analisando processos...")

        try:
            procs = []
            for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
                try:
                    ram = p.memory_info().rss / (1024 ** 2)
                    procs.append((ram, p.pid, p.name()))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            procs.sort(reverse=True)

            self.log(f"  {'PID':<8} {'RAM(MB)':>9}  Nome")
            self.log(f"  {'-'*8} {'-'*9}  {'-'*35}")

            for ram, pid, name in procs[:10]:
                self.log(f"  {pid:<8} {ram:>8.1f}MB  {name}")

        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Analise concluida.")
            self.log("")

    # ============================================================
    # INFORMACOES DE BATERIA
    # ============================================================
    def battery_info(self):
        self.log_title("Informacoes de Bateria")
        self._progress_start("Lendo bateria...")

        try:
            bat = psutil.sensors_battery()
            if bat is None:
                self.log_warn("Nenhuma bateria detectada. Pode ser um desktop ou bateria nao suportada.")
            else:
                status  = "Carregando" if bat.power_plugged else "Descarregando"
                percent = bat.percent

                self.log(f"  Nivel         : {percent:.1f}%")
                self.log(f"  Status        : {status}")

                if bat.secsleft and bat.secsleft > 0 and not bat.power_plugged:
                    h, rem = divmod(bat.secsleft, 3600)
                    m, _   = divmod(rem, 60)
                    self.log(f"  Tempo restante: {h:02d}h {m:02d}m")
                else:
                    self.log("  Tempo restante: N/D (plugado ou calculando)")

        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Leitura concluida.")
            self.log("")