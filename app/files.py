from config import *
from app.app import App


class Files(App):
    def __init__(self):
        super().__init__()

    # ============================================================
    # LIMPEZA DE TEMPORARIOS
    # Envolve Python para calcular tamanho antes de deletar
    # ============================================================
    def clean_temp(self):
        user_temp    = os.environ.get("TEMP", r"C:\Users\Public\AppData\Local\Temp")
        windows_temp = r"C:\Windows\Temp"

        for folder, titulo in (
            (user_temp,    "LIMPEZA DE TEMP DO USUARIO"),
            (windows_temp, "LIMPEZA DE TEMP DO WINDOWS"),
        ):
            size_gb, file_count = self.get_folder_info(folder)
            self.log("")
            self.log("=" * 50)
            self.log(titulo.center(50))
            self.log("=" * 50)
            self.log(f"Pasta           : {folder}")
            self.log("-" * 50)
            self.log(f"Total arquivos  : {file_count}")
            self.log(f"Tamanho ocupado : {size_gb} GB")
            self.log("")
            self.run_command(
                f"Limpando {titulo}",
                rf'del /q /f /s "{folder}\*.*"'
            )

    # ============================================================
    # LIMPEZA DE PREFETCH - delega ao COMMANDS
    # ============================================================
    def clean_prefetch(self):
        folder = r"C:\Windows\Prefetch"
        size_gb, file_count = self.get_folder_info(folder)
        self.log("")
        self.log("=" * 50)
        self.log("PASTA PREFETCH".center(50))
        self.log("=" * 50)
        self.log(f"Pasta           : {folder}")
        self.log(f"Total arquivos  : {file_count}")
        self.log(f"Tamanho ocupado : {size_gb} GB")
        self.log("")
        self.run_command("Limpando Prefetch", COMMANDS["clean_prefetch"])

    # ============================================================
    # CACHE DO WINDOWS UPDATE - delega ao COMMANDS
    # ============================================================
    def clean_windows_update(self):
        folder = r"C:\Windows\SoftwareDistribution\Download"
        size_gb, file_count = self.get_folder_info(folder)
        self.log("")
        self.log("=" * 50)
        self.log("CACHE DO WINDOWS UPDATE".center(50))
        self.log("=" * 50)
        self.log(f"Pasta           : {folder}")
        self.log(f"Total arquivos  : {file_count}")
        self.log(f"Tamanho ocupado : {size_gb} GB")
        self.log("")
        self.run_command("Limpando cache do Windows Update", COMMANDS["clean_windows_update"])