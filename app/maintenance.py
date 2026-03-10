from config import *
from app.app import App


class Maintenance(App):
    """Manutencao avancada: defrag, TRIM, GPO, Store, .NET."""

    def __init__(self):
        super().__init__()

    def defrag_hdd(self):
        self.log_warn("Use apenas em HDs mecanicos (HDD). NAO use em SSD.")
        self.run_command("Desfragmentar disco C: (HDD)", COMMANDS["defrag_hdd"])

    def trim_ssd(self):
        self.log_warn("Use apenas em SSDs. NAO use em HDD.")
        self.run_command("Otimizar SSD C: (TRIM)", COMMANDS["trim_ssd"])

    def reset_gpo(self):
        self.run_command("Resetar Politicas de Grupo", COMMANDS["reset_gpo"])

    def repair_store(self):
        self.run_command("Reparar Microsoft Store", COMMANDS["repair_store"])

    def verify_dotnet(self):
        self.run_command("Verificar .NET Framework instalado", COMMANDS["verify_dotnet"])

    # Metodos de manutencao principal que estavam espalhados em outros modulos
    def run_sfc(self):
        self.log_warn("SFC pode demorar varios minutos. Nao feche o programa.")
        self.run_command("Verificar Sistema (SFC)", COMMANDS["run_sfc"])

    def run_dism(self):
        self.log_warn("DISM pode demorar varios minutos e requer internet ativa.")
        self.run_command("Reparar Windows (DISM)", COMMANDS["run_dism"])

    def run_chkdsk(self):
        self.log_warn("CHKDSK sera agendado para o proximo boot do sistema.")
        self.run_command("Verificar Disco (CHKDSK)", COMMANDS["run_chkdsk"])

    def restart_print_spooler(self):
        self.run_command("Reiniciando Spooler de Impressao", COMMANDS["restart_print_spooler"])

    def check_disk_surface(self):
        self.log_warn("Verificacao fisica pode demorar. O sistema pode precisar reiniciar.")
        self.run_command("Verificar Superficie do Disco", COMMANDS["check_disk_surface"])