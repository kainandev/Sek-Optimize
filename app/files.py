from config import *
from app.app import App


class Files(App):
    """Limpeza de arquivos temporarios e caches."""

    def __init__(self):
        super().__init__()

    # ============================================================
    # TEMP DO USUARIO E DO WINDOWS
    # Calcula tamanho antes de deletar para exibir no log.
    # ============================================================
    def clean_temp(self):
        user_temp    = os.environ.get("TEMP", r"C:\Users\Public\Temp")
        windows_temp = r"C:\Windows\Temp"

        for folder, titulo in (
            (user_temp,    "TEMP DO USUARIO"),
            (windows_temp, "TEMP DO WINDOWS"),
        ):
            size_gb, file_count = self.get_folder_info(folder)
            self.log("")
            self.log("=" * 50)
            self.log(titulo.center(50))
            self.log("=" * 50)
            self.log(f"  Pasta           : {folder}")
            self.log(f"  Total arquivos  : {file_count}")
            self.log(f"  Tamanho ocupado : {size_gb} GB")
            self.run_command(
                f"Limpando {titulo}",
                rf'del /q /f /s "{folder}\*.*"',
            )

    # ============================================================
    # PREFETCH
    # ============================================================
    def clean_prefetch(self):
        folder = r"C:\Windows\Prefetch"
        size_gb, file_count = self.get_folder_info(folder)
        self.log(f"  Pasta           : {folder}")
        self.log(f"  Total arquivos  : {file_count}")
        self.log(f"  Tamanho ocupado : {size_gb} GB")
        self.run_command("Limpando Prefetch", COMMANDS["clean_prefetch"])

    # ============================================================
    # CACHE DO WINDOWS UPDATE
    # ============================================================
    def clean_windows_update(self):
        folder = r"C:\Windows\SoftwareDistribution\Download"
        size_gb, file_count = self.get_folder_info(folder)
        self.log(f"  Pasta           : {folder}")
        self.log(f"  Total arquivos  : {file_count}")
        self.log(f"  Tamanho ocupado : {size_gb} GB")
        self.run_command("Limpando cache do Windows Update", COMMANDS["clean_windows_update"])

    # ============================================================
    # LIXEIRA
    # ============================================================
    def clean_recycle_bin(self):
        self.run_command("Esvaziando lixeira", COMMANDS["clean_recycle_bin"])

    # ============================================================
    # EVENT LOGS
    # ============================================================
    def clean_event_logs(self):
        self.log_warn("Esta acao apaga os logs de eventos (System, Application, Security).")
        self.run_command("Limpando Event Logs", COMMANDS["clean_event_logs"])

    # ============================================================
    # CACHE DE MINIATURAS (thumbcache)
    # ============================================================
    def clean_thumbnail_cache(self):
        self.run_command("Limpando cache de miniaturas", COMMANDS["clean_thumbnail_cache"])

    # ============================================================
    # CACHE DO MICROSOFT EDGE
    # ============================================================
    def clean_edge_cache(self):
        self.log_warn("O Microsoft Edge sera encerrado antes da limpeza.")
        self.run_command("Limpando cache do Edge", COMMANDS["clean_edge_cache"])

    # ============================================================
    # CACHE DO GOOGLE CHROME
    # ============================================================
    def clean_chrome_cache(self):
        self.log_warn("O Google Chrome sera encerrado antes da limpeza.")
        self.run_command("Limpando cache do Chrome", COMMANDS["clean_chrome_cache"])

    # ============================================================
    # WINDOWS ERROR REPORTING (WER)
    # ============================================================
    def clean_wer(self):
        self.run_command("Limpando relatorios de erro (WER)", COMMANDS["clean_wer"])

    # ============================================================
    # RESTORE POINTS ANTIGOS
    # ============================================================
    def clean_restore_points(self):
        self.log_warn("Apenas o ponto de restauracao mais antigo sera removido.")
        self.run_command("Removendo restore point antigo", COMMANDS["clean_restore_points"])