from config import *
from app.app import App


class Optmize(App):
    def __init__(self):
        super().__init__()

    def disable_transparency(self):
        self.run_command("Desativando transparencias", COMMANDS["disable_transparency"])

    def disable_gamemode(self):
        self.run_command("Desativando Game Mode e Game Bar", COMMANDS["disable_gamemode"])

    def power_plan(self):
        self.run_command("Ajustando plano de energia", COMMANDS["power_plan"])

    def visual_effects(self):
        self.run_command("Ajustando efeitos visuais", COMMANDS["visual_effects"])

    def disable_services(self):
        self.run_command("Desativando servicos pesados (SysMain)", COMMANDS["disable_services"])

    def restart_explorer(self):
        self.run_command("Reiniciando Explorer", COMMANDS["restart_explorer"])

    def disable_fast_startup(self):
        self.run_command("Desativando Inicializacao Rapida", COMMANDS["disable_fast_startup"])

    def kill_background_tasks(self):
        self.run_command("Encerrando tarefas em segundo plano", COMMANDS["kill_background_tasks"])

    def check_disk_health(self):
        self.run_command("Verificando saude do disco (SMART)", COMMANDS["check_disk_health"])

    def disk_info(self):
        self.run_command("Informacoes do disco", COMMANDS["disk_info"])

    def check_disk_surface(self):
        self.run_command("Verificando superficie do disco", COMMANDS["check_disk_surface"])

    def restart_print_spooler(self):
        self.run_command("Reiniciando spooler de impressao", COMMANDS["restart_print_spooler"])

    def run_sfc(self):
        self.run_command("Executando SFC", COMMANDS["run_sfc"])

    def run_dism(self):
        self.run_command("Executando DISM", COMMANDS["run_dism"])

    def run_chkdsk(self):
        self.run_command("Agendando verificacao de disco (CHKDSK)", COMMANDS["run_chkdsk"])

    def disk_usage_report(self):
        """Relatorio de uso do disco C: via Python puro."""
        usage = psutil.disk_usage("C:/")
        total   = round(usage.total / (1024 ** 3), 1)
        used    = round(usage.used  / (1024 ** 3), 1)
        free    = round(usage.free  / (1024 ** 3), 1)
        percent = usage.percent

        self.log("")
        self.log("=" * 44)
        self.log("USO DO DISCO (C:)".center(44))
        self.log("=" * 44)
        self.log(f"Tamanho total : {total} GB")
        self.log(f"Em uso        : {used} GB")
        self.log(f"Livre         : {free} GB")
        self.log(f"Ocupacao      : {percent}%")
        self.log("=" * 44)

    # ============================================================
    # OTIMIZACAO COMPLETA
    # Roda em sequencia todas as otimizacoes seguras
    # ============================================================
    def optimize_all(self):
        self.log_info("Iniciando otimizacao completa...")
        self.disable_transparency()
        self.disable_gamemode()
        self.power_plan()
        self.visual_effects()
        self.disable_services()
        self.clean_temp()
        self.flush_dns()
        self.log_info("Otimizacao completa finalizada!")

    # ============================================================
    # MAS - executa em janela externa separada
    # ============================================================
    def run_massgrave(self):
        self.log("Abrindo Microsoft Activation Scripts (MAS)...")
        cmd = (
            r'start "" cmd.exe /c powershell -NoLogo -NoProfile -Command '
            r'"iwr -useb https://get.activated.win | iex"'
        )
        subprocess.Popen(cmd, shell=True)

    # ============================================================
    # RELATORIO DO SISTEMA via WMI (Python puro)
    # ============================================================
    def run_system_report(self):
        if pythoncom is None:
            self.log_error("pythoncom nao disponivel. Instale pywin32.")
            return
        pythoncom.CoInitialize()
        try:
            self.log("")
            self.log("=" * 60)
            self.log("RELATORIO DO SISTEMA".center(60))
            self.log("=" * 60)

            # --- Memoria ---
            slots, max_ram = get_ram_capability()
            modules = get_ram_modules()
            mem_lines = [
                "|- Capacidade",
                f"|  |- Slots disponiveis : {slots}",
                f"|  +- Maximo suportado  : {max_ram} GB",
                "+- Modulos",
            ]
            for i, m in enumerate(modules):
                last   = (i == len(modules) - 1)
                branch = "+--" if last else "|--"
                indent = "   " if last else "|  "
                mem_lines += [
                    f"{branch} {m['Slot']}",
                    f"{indent}|- Capacidade (GB)  : {m['Capacidade (GB)']}",
                    f"{indent}|- Velocidade (MHz) : {m['Velocidade (MHz)']}",
                    f"{indent}|- Fabricante       : {m['Fabricante']}",
                    f"{indent}|- Tipo             : {m['Tipo']}",
                    f"{indent}+- Serial           : {m['Serial']}",
                ]
            self.log_tree("MEMORIA", mem_lines)

            # --- CPU ---
            cpu = get_cpu_info()
            self.log_tree("CPU", [
                f"|- Modelo          : {cpu['Modelo']}",
                f"|- Arquitetura     : {cpu['Arquitetura']}",
                f"|- Bits            : {cpu['Bits']}",
                f"|- Frequencia Base : {cpu['Frequencia Base']}",
                f"+- Nucleos         : {cpu['Nucleos']}",
            ])

            # --- GPU ---
            gpus = get_gpu_info()
            gpu_lines = []
            for i, g in enumerate(gpus):
                last   = (i == len(gpus) - 1)
                branch = "+--" if last else "|--"
                indent = "   " if last else "|  "
                gpu_lines += [
                    f"{branch} {g['Nome']}",
                    f"{indent}|- VRAM (MB) : {g['VRAM (MB)']}",
                    f"{indent}+- Driver    : {g['Driver']}",
                ]
            self.log_tree("GPU", gpu_lines)

            # --- Discos ---
            disks = get_disks()
            disk_lines = []
            for i, d in enumerate(disks):
                last   = (i == len(disks) - 1)
                branch = "+--" if last else "|--"
                indent = "   " if last else "|  "
                disk_lines += [
                    f"{branch} {d['Modelo']}",
                    f"{indent}|- Interface    : {d['Interface']}",
                    f"{indent}|- Tamanho (GB) : {d['Tamanho (GB)']}",
                    f"{indent}+- Serial       : {d['Serial']}",
                ]
            self.log_tree("DISCOS", disk_lines)

        finally:
            pythoncom.CoUninitialize()

        self.log("")
        self.log("=" * 60)