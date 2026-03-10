from config import *
from app.app import App


class Optmize(App):
    """Otimizacoes de desempenho e configuracoes do sistema."""

    def __init__(self):
        super().__init__()

    # Cada metodo delega para run_command com a chave de COMMANDS.
    # Para alterar o comando, edite apenas o dict COMMANDS em config.py.

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
        self.run_command("Saude do disco (SMART)", COMMANDS["check_disk_health"])

    def disk_info(self):
        self.run_command("Informacoes do disco", COMMANDS["disk_info"])

    def check_disk_surface(self):
        self.run_command("Verificando superficie do disco", COMMANDS["check_disk_surface"])

    def restart_print_spooler(self):
        self.run_command("Reiniciando spooler de impressao", COMMANDS["restart_print_spooler"])

    def disable_hibernation(self):
        self.run_command("Desativando hibernacao", COMMANDS["disable_hibernation"])

    def disable_search_indexing(self):
        self.run_command("Desativando indexacao de busca", COMMANDS["disable_search_indexing"])

    def list_installed_programs(self):
        self.log_warn("Este comando pode demorar alguns segundos.")
        self.run_command("Programas instalados", COMMANDS["list_installed_programs"])

    def check_drivers(self):
        self.run_command("Drivers instalados", COMMANDS["check_drivers"])

    def check_updates_hotfix(self):
        self.run_command("Atualizacoes recentes (HotFix)", COMMANDS["check_updates_hotfix"])

    # Privatidade
    def disable_telemetry(self):
        self.run_command("Desativando telemetria", COMMANDS["disable_telemetry"])

    def disable_cortana(self):
        self.run_command("Desativando Cortana", COMMANDS["disable_cortana"])

    def disable_xbox_dvr(self):
        self.run_command("Desativando Xbox Game DVR", COMMANDS["disable_xbox_dvr"])

    def disable_remote_desktop(self):
        self.run_command("Desativando Remote Desktop", COMMANDS["disable_remote_desktop"])

    def list_startup_programs(self):
        self.run_command("Programas na inicializacao", COMMANDS["list_startup_programs"])

    def export_users(self):
        self.run_command("Usuarios do sistema", COMMANDS["export_users"])

    def defender_quick_scan(self):
        self.run_command("Windows Defender - Scan Rapido", COMMANDS["defender_quick_scan"])

    # Relatorio completo do sistema via WMI
    def run_system_report(self):
        if pythoncom is None:
            self.log_error("pythoncom nao disponivel. Instale pywin32.")
            return
        pythoncom.CoInitialize()
        self._progress_start("Gerando relatorio...")
        try:
            self.log("")
            self.log("=" * 62)
            self.log("RELATORIO DO SISTEMA".center(62))
            self.log("=" * 62)

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

            cpu = get_cpu_info()
            self.log_tree("CPU", [
                f"|- Modelo          : {cpu['Modelo']}",
                f"|- Arquitetura     : {cpu['Arquitetura']}",
                f"|- Bits            : {cpu['Bits']}",
                f"|- Frequencia Base : {cpu['Frequencia Base']}",
                f"+- Nucleos         : {cpu['Nucleos']}",
            ])

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
            self._progress_stop()
            pythoncom.CoUninitialize()
            self.log("")
            self.log("=" * 62)

    # ============================================================
    # RELATORIO DE USO DE DISCO (Python puro, sem shell)
    # ============================================================
    def disk_usage_report(self):
        usage   = psutil.disk_usage("C:/")
        total   = round(usage.total / (1024 ** 3), 1)
        used    = round(usage.used  / (1024 ** 3), 1)
        free    = round(usage.free  / (1024 ** 3), 1)
        percent = usage.percent

        self.log_title("Uso do Disco C:")
        self.log(f"  Tamanho total : {total} GB")
        self.log(f"  Em uso        : {used} GB")
        self.log(f"  Livre         : {free} GB")
        self.log(f"  Ocupacao      : {percent}%")
        self.log_sep()
        self.log_ok("Concluido.")
        self.log("")

    # ============================================================
    # OTIMIZACAO COMPLETA
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
        self.log_ok("Otimizacao completa finalizada!")

    # ============================================================
    # MAS - executa em janela externa separada
    # ============================================================
    def run_massgrave(self):
        self.log_info("Abrindo Microsoft Activation Scripts (MAS)...")
        cmd = (
            r'start "" cmd.exe /c powershell -NoLogo -NoProfile -Command '
            r'"iwr -useb https://get.activated.win | iex"'
        )
        subprocess.Popen(cmd, shell=True)