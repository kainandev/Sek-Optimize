from app.app import App
from app.files import Files
from app.network import Network


class Optmize(App):
	def __init__(self):
		super().__init__(self)

	def disable_transparency(self):
        self.run_command("Desativando transparências",
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v EnableTransparency /t REG_DWORD /d 0 /f'
        )

    def disable_gamemode(self):
        self.run_command(
            "Desativando Game Mode e Game Bar",
            r'reg add "HKCU\Software\Microsoft\GameBar" /v AutoGameModeEnabled /t REG_DWORD /d 0 /f'
            r' & reg add "HKCU\System\GameConfigStore" /v GameDVR_Enabled /t REG_DWORD /d 0 /f'
        )

    def power_plan(self):
        self.run_command("Ajustando plano de energia", "powercfg -setactive SCHEME_MIN")

    def visual_effects(self):
        self.run_command(
            "Ajustando efeitos visuais para desempenho",
            r'reg add "HKCU\Control Panel\Desktop" /v DragFullWindows /t REG_SZ /d 0 /f'
            r' & reg add "HKCU\Control Panel\Desktop" /v MenuShowDelay /t REG_SZ /d 0 /f'
            r' & reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" '
            r'/v VisualFXSetting /t REG_DWORD /d 2 /f'
        )

    def disable_services(self):
        self.run_command(
            "Desativando serviços pesados (SysMain)",
            r'sc stop SysMain & sc config SysMain start= disabled'
        )

    def optimize_all(self):
        self.log("Iniciando otimização completa...")
        self.disable_transparency()
        self.disable_gamemode()
        self.power_plan()
        self.visual_effects()
        self.disable_services()
        Files().clean_temp()
        Network().flush_dns()
        self.log("Otimização completa finalizada!")

    def run_massgrave(self):
        self.log("Abrindo Microsoft Activation Scripts (MAS)...")

        cmd = (
            r'start "" cmd.exe /c powershell -NoLogo -NoProfile -Command '
            r'"iwr -useb https://get.activated.win | iex"'
        )

        subprocess.Popen(cmd, shell=True)