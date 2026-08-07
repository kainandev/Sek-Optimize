from config import *
from app.app import App
from util.schemes import SchemeBuilder

# Codigos de erro do Gerenciador de Dispositivos (Win32_PnPEntity.ConfigManagerErrorCode).
# Tabela oficial da Microsoft (CM_PROB_*), traduzida.
_PNP_ERROR_CODES = {
    1:  "Dispositivo nao configurado corretamente",
    3:  "Driver corrompido ou memoria insuficiente",
    9:  "Dados de configuracao da placa invalidos (barramento incorreto)",
    10: "Dispositivo nao pode iniciar",
    12: "Recursos livres insuficientes",
    14: "Requer reinicializacao do computador para funcionar",
    16: "Nao foi possivel identificar todos os recursos do dispositivo",
    18: "Reinstalar os drivers deste dispositivo",
    19: "Registro do Windows corrompido para este dispositivo",
    21: "Sistema esta removendo o dispositivo (aguarde)",
    22: "Dispositivo desativado pelo usuario",
    24: "Dispositivo ausente, com defeito ou desconectado",
    28: "Drivers deste dispositivo nao instalados",
    29: "Dispositivo desativado pelo firmware (BIOS/UEFI)",
    31: "Dispositivo nao esta funcionando corretamente (driver incompleto/config)",
    32: "Driver desativado (tipo de inicializacao desabilitado)",
    33: "Windows nao consegue determinar quais recursos o dispositivo precisa",
    34: "Windows nao consegue determinar as configuracoes do dispositivo",
    35: "Firmware do sistema nao inclui informacoes suficientes p/ configurar",
    36: "Dispositivo requer IRQ que nao pode ser atribuido",
    37: "Driver retornou falha na inicializacao",
    38: "Driver anterior ainda esta carregado na memoria",
    39: "Driver ausente ou corrompido",
    40: "Registro do servico do driver corrompido",
    41: "Driver carregado, mas o dispositivo nao foi encontrado",
    42: "Dispositivo duplicado detectado",
    43: "Windows parou o dispositivo por ele reportar problemas",
    44: "Aplicativo ou servico desligou o dispositivo",
    45: "Dispositivo removido fisicamente, mas ainda instalado no sistema",
    46: "Dispositivo indisponivel (sistema esta desligando)",
    47: "Dispositivo preparado para remocao segura, mas ainda nao removido",
    48: "Driver bloqueado por incompatibilidade conhecida",
    49: "Sistema nao pode mais adicionar dispositivos (arvore de registro cheia)",
    52: "Windows nao pode verificar a assinatura digital do driver",
}


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
        self.log_title("Saude do Disco (SMART)")
        self._progress_start("Consultando Storage Reliability Counters (WMI)...")
        try:
            disks = SchemeBuilder()._collect_disk_health()
            if not disks:
                self.log_warn("Nenhum disco fisico detectado ou WMI indisponivel.")
            for d in disks:
                lines = [
                    f"|- Status         : {d.get('health_status', 'N/A')}",
                    f"|- Tipo           : {d.get('media_type', 'N/A')} / {d.get('bus_type', 'N/A')}",
                    f"|- Capacidade     : {d.get('size_gb', 'N/A')} GB",
                    f"|- Serial         : {d.get('serial_number', 'N/A')}",
                ]

                wear = d.get("wear_pct")
                if wear is not None:
                    lines.append(f"|- Desgaste (vida usada) : {wear}%")

                poh = d.get("power_on_hours")
                if poh is not None:
                    dias = d.get("power_on_days")
                    dias_str = f" (~{dias} dias)" if dias is not None else ""
                    lines.append(f"|- Horas ligado   : {poh}h{dias_str}")

                temp = d.get("temperature_c")
                if temp is not None:
                    lines.append(f"|- Temperatura    : {temp} C")

                note = d.get("reliability_unavailable")
                if note:
                    lines.append(f"+- Aviso          : {note}")
                else:
                    lines[-1] = lines[-1].replace("|-", "+-", 1)

                self.log_tree(d.get("model", "Disco"), lines)
        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log_sep()
            self.log_ok("Verificacao concluida.")
            self.log("")

    def disk_info(self):
        self.run_command("Informacoes do disco", COMMANDS["disk_info"])

    def list_scheduled_tasks(self):
        self.run_command("Tarefas Agendadas", COMMANDS["list_scheduled_tasks"])

    def check_activation_status(self):
        self.run_command("Status de Ativacao do Windows", COMMANDS["check_activation_status"])

    def check_driver_errors(self):
        self.log_title("Drivers com Erro")
        self._progress_start("Consultando dispositivos (WMI)...")
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            problems = [
                d for d in c.Win32_PnPEntity()
                if (getattr(d, "ConfigManagerErrorCode", 0) or 0) != 0
            ]

            if not problems:
                self.log_ok("Nenhum dispositivo com erro de driver detectado.")

            for d in problems:
                code = d.ConfigManagerErrorCode
                self.log(f"[{d.Name or d.DeviceID or 'Dispositivo desconhecido'}]")
                self.log(f"  Codigo de erro : {code} - {_PNP_ERROR_CODES.get(code, 'Codigo desconhecido')}")
                self.log(f"  Status         : {d.Status or 'N/A'}")
                self.log(f"  Device ID      : {d.DeviceID or 'N/A'}")
                self.log("")
        except Exception as e:
            self.log_error(str(e))
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
            self._progress_stop()
            self.log_sep()
            self.log_ok("Verificacao concluida.")
            self.log("")

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