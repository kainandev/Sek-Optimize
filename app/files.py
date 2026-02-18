from app.app import App

class Files(App):
	def __init__(self):
		super().__init__(self)

	def clean_temp(self):
        user_temp = os.environ.get("TEMP")
        windows_temp = r"C:\Windows\Temp"

        # ================= TEMP DO USUÁRIO =================
        size_gb_user, file_count_user = self.get_folder_info(user_temp)

        user_header = [
            "",
            "=" * 50,
            "        LIMPEZA DE ARQUIVOS TEMP (USUÁRIO)",
            "=" * 50,
            f"Pasta analisada : {user_temp}",
            "-" * 50,
            f"Total de arquivos : {file_count_user}",
            f"Tamanho ocupado  : {size_gb_user} GB",
            "",
        ]

        for line in user_header:
            self.log(line)

        self.run_command(
            "Iniciando limpeza do TEMP do usuário",
            rf'del /q /f /s "{user_temp}\*.*"'
        )

        # ================= TEMP DO WINDOWS =================
        size_gb_win, file_count_win = self.get_folder_info(windows_temp)

        win_header = [
            "",
            "=" * 50,
            "        LIMPEZA TEMP DO WINDOWS",
            "=" * 50,
            f"Pasta analisada : {windows_temp}",
            "-" * 50,
            f"Total de arquivos : {file_count_win}",
            f"Tamanho ocupado  : {size_gb_win} GB",
            "",
        ]

        for line in win_header:
            self.log(line)

        self.run_command(
            "Iniciando limpeza do TEMP do Windows",
            rf'del /q /f /s "{windows_temp}\*.*"'
        )