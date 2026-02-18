from config import *

class App:
    def __init__(self):
        self.gui = None
        self.start_time = datetime.now()
        self.log_file = self.gerar_log_file()

        self.show_fetch()

    def set_gui(self, gui):
        self.gui = gui

    # ============================================
    # LOG CENTRAL
    # ============================================
    def gerar_log_file(self):
        hostname = socket.gethostname()
        data_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nome = f"{hostname}-{data_hora}.log"

        pasta_logs = "logs"
        os.makedirs(pasta_logs, exist_ok=True)

        return os.path.join(pasta_logs, nome)

    def log(self, msg):
        timestamp = datetime.now().strftime("[%d/%m/%Y %H:%M:%S] ")
        texto = timestamp + msg

        # Interface
        self.gui.add_log(texto)

        # Arquivo
        with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
            f.write(texto + "\n")


    def _decode(self, raw):
        try:
            return raw.decode("cp850", errors="replace")
        except Exception:
            return raw.decode("latin-1", errors="replace")


    def run_command(self, desc, cmd):
        self.log_title("" + desc)

        with subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        ) as proc:
            for raw in proc.stdout:
                line = self._decode(raw).replace("\r\n", "\n")
                self.log(line.rstrip("\n"))

        self.log('')
        self.log_info("Finalizado...")
        self.log('')


    # ============================================
    # FUNÇÕES INDIVIDUAIS
    # ============================================



    def flush_dns(self):
        self.run_command("Limpando DNS", "ipconfig /flushdns")

    def run_sfc(self):
        self.run_command("Executando SFC", "sfc /scannow")

    def run_dism(self):
        self.run_command("Executando DISM", "dism /online /cleanup-image /restorehealth")

    def restart_explorer(self):
        self.run_command(
            "Reiniciando Explorer",
            "taskkill /f /im explorer.exe & start explorer.exe"
        )

    def run_systeminfo(self):
        self.run_command("SystemInfo", "systeminfo")

    def run_tasklist(self):
        self.run_command("Lista de Processos", "tasklist")

    def run_driverquery(self):
        self.run_command("Lista de Drivers", "driverquery")

    def run_chkdsk(self):
        self.run_command(
            "Agendando verificação de disco (CHKDSK)",
            r'chkdsk C: /f /r'
        )

    def kill_background_tasks(self):
        self.run_command(
            "Encerrando processos em segundo plano",
            r'taskkill /f /im OneDrive.exe & taskkill /f /im Teams.exe'
        )

    def reset_network(self):
        self.run_command(
            "Resetando configurações de rede",
            r'netsh int ip reset & netsh winsock reset & ipconfig /flushdns'
        )

    def disable_fast_startup(self):
        self.run_command(
            "Desativando Inicialização Rápida",
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" '
            r'/v HiberbootEnabled /t REG_DWORD /d 0 /f'
        )

    def clean_windows_update(self):
        folder = r"C:\Windows\SoftwareDistribution\Download"
        size_gb, file_count = self.get_folder_info(folder)

        table = [
            "==============================================",
            "     CACHE DO WINDOWS UPDATE              ",
            "==============================================",
            f"Pasta            : {folder}",
            f"Total de arquivos: {file_count}",
            f"Tamanho ocupado : {size_gb} GB",
            ""
        ]

        for line in table:
            self.log(line)

        self.run_command(
            "Limpando cache do Windows Update",
            r'net stop wuauserv & '
            r'del /q /f /s C:\Windows\SoftwareDistribution\Download\*.* & '
            r'net start wuauserv'
        )

    def clean_prefetch(self):
        folder = r"C:\Windows\Prefetch"
        size_gb, file_count = self.get_folder_info(folder)

        table = [
            "==============================================",
            "        PASTA PREFETCH                    ",
            "==============================================",
            f"Pasta            : {folder}",
            f"Total de arquivos: {file_count}",
            f"Tamanho ocupado : {size_gb} GB",
            ""
        ]

        for line in table:
            self.log(line)

        self.run_command(
            "Limpando Prefetch do Windows",
            r'del /q /f /s C:\Windows\Prefetch\*.*'
        )

    def disk_usage_report(self):
        usage = psutil.disk_usage("C:/")

        total = round(usage.total / (1024**3), 1)
        used = round(usage.used / (1024**3), 1)
        free = round(usage.free / (1024**3), 1)
        percent = usage.percent

        table = (
            "\n============================================\n"
            "          USO DO DISCO (C:)                \n"
            "============================================\n"
            f"Tamanho total : {total} GB\n"
            f"Em uso        : {used} GB\n"
            f"Livre         : {free} GB\n"
            f"Ocupação      : {percent}%\n"
            "============================================\n"
        )

        self.log(table)

    def check_disk_surface(self):
        self.run_command(
            "Verificando superfície do disco (CHKDSK)",
            "chkdsk C: /f /r"
        )

    def disk_errors(self):
        self.run_command(
            "Verificando erros lógicos no disco",
            'wmic diskdrive get status'
        )

    def disk_info(self):
        self.run_command(
            "Informações detalhadas do disco",
            'wmic diskdrive get model,serialnumber,size,mediatype'
        )

    def check_disk_health(self):
        self.run_command(
            "Verificando saúde do disco (SMART)",
            'wmic diskdrive get model,status,interfacetype,mediatype'
        )

    def restart_print_spooler(self):
        self.run_command(
            "Reiniciando spooler de impressão",
            r'net stop spooler & '
            r'del /q /f /s C:\Windows\System32\spool\PRINTERS\*.* & '
            r'net start spooler'
        )

    def run_system_report(self):
        pythoncom.CoInitialize()  # Inicializa COM nesta thread
        try:
            self.log("")
            self.log("=" * 60)
            self.log("RELATÓRIO DO SISTEMA".center(60))
            self.log("=" * 60)

            self.system_report_running = True

            # ================= MEMÓRIA =================
            slots, max_ram = get_ram_capability()
            modules = get_ram_modules()

            mem_lines = [
                "├── Capacidade",
                f"│   ├── Slots disponíveis : {slots}",
                f"│   └── Máximo suportado  : {max_ram} GB",
                "├── Módulos"
            ]

            for i, m in enumerate(modules):
                last = (i == len(modules) - 1)
                branch = "└──" if last else "├──"
                indent = "    " if last else "│   "
                mem_lines.extend([
                    f"{branch} {m['Slot']}",
                    f"{indent}├── Capacidade (GB)  : {m['Capacidade (GB)']}",
                    f"{indent}├── Velocidade (MHz) : {m['Velocidade (MHz)']}",
                    f"{indent}├── Fabricante       : {m['Fabricante']}",
                    f"{indent}├── Tipo             : {m['Tipo']}",
                    f"{indent}└── Serial           : {m['Serial']}",
                ])

            self.log_tree("MEMÓRIA", mem_lines)

            # ================= CPU =================
            cpu = get_cpu_info()
            self.log_tree("CPU", [
                f"├── Modelo          : {cpu['Modelo']}",
                f"├── Arquitetura     : {cpu['Arquitetura']}",
                f"├── Bits            : {cpu['Bits']}",
                f"├── Frequência Base : {cpu['Frequência Base']}",
                f"└── Núcleos         : {cpu['Núcleos']}",
            ])

            # ================= GPU =================
            gpus = get_gpu_info()
            gpu_lines = []
            for i, g in enumerate(gpus):
                last = (i == len(gpus) - 1)
                branch = "└──" if last else "├──"
                indent = "    " if last else "│   "
                gpu_lines.extend([
                    f"{branch} {g['Nome']}",
                    f"{indent}├── VRAM (MB) : {g['VRAM (MB)']}",
                    f"{indent}└── Driver    : {g['Driver']}",
                ])
            self.log_tree("GPU", gpu_lines)

            # ================= DISCOS =================
            disks = get_disks()
            disk_lines = []
            for i, d in enumerate(disks):
                last = (i == len(disks) - 1)
                branch = "└──" if last else "├──"
                indent = "    " if last else "│   "
                disk_lines.extend([
                    f"{branch} {d['Modelo']}",
                    f"{indent}├── Interface    : {d['Interface']}",
                    f"{indent}├── Tamanho (GB) : {d['Tamanho (GB)']}",
                    f"{indent}└── Serial       : {d['Serial']}",
                ])
            self.log_tree("DISCOS", disk_lines)

        finally:
            self.system_report_running = False
            pythoncom.CoUninitialize()  # Finaliza COM ao sair da thread

        self.log("")
        self.log("=" * 60)


    # ============================================
    # MAPEAMENTO DOS BOTÕES
    # ============================================
    def execute_button(self, index):
        action = ACTIONS.get(index)
        if not action:
            return

        handler_name = action["handler"]
        handler = getattr(self, handler_name, None)

        if not handler:
            self.log(f"Ação '{handler_name}' não implementada.")
            return

        threading.Thread(target=handler).start()


    # ============================================
    # EXECUTAR COMANDO DIGITADO (TERMINAL)
    # ============================================
    def _run_command(self, command):
        self.log(f"> {command}")

        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            for raw in proc.stdout:
                line = self._decode(raw).rstrip("\r\n")
                if line:
                    self.log(line)

            proc.wait()

        except Exception as e:
            self.log(f"ERRO: {e}")



    # ============================================
    # COMANDO DIGITADO PELO TERMINAL DA GUI
    # ============================================
    def run_custom_command(self, command):
        self._run_command(command)

    # ============================================
    # Obtem informações de uma pasta especifica.
    # ============================================
    def get_folder_info(self, folder_path):
        total_size = 0
        total_files = 0

        for root, dirs, files in os.walk(folder_path):
            total_files += len(files)
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    total_size += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass

        size_gb = total_size / (1024 ** 3)
        return round(size_gb, 2), total_files