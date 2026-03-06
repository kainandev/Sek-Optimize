from config import *
from app.app import App


class FastFetch(App):
    def __init__(self):
        super().__init__()

    # ============================================================
    # FAST FETCH - exibido uma vez quando a GUI fica pronta
    # ============================================================
    def show_fetch(self):
        inicio = self.start_time.strftime("%d/%m/%Y %H:%M:%S")

        usuario     = getpass.getuser()
        hostname    = socket.gethostname()
        sistema     = platform.system()
        release     = platform.release()
        version     = platform.version()
        arquitetura = platform.machine()
        processador = platform.processor()
        python_ver  = platform.python_version()

        cpu_cores   = psutil.cpu_count(logical=False)
        cpu_threads = psutil.cpu_count(logical=True)
        ram_total   = round(psutil.virtual_memory().total / (1024 ** 3), 1)

        boot_mode = (
            "UEFI" if os.path.exists(r"C:\Windows\System32\SecureBoot.exe")
            else "Legacy"
        )

        uptime_seconds = time.time() - psutil.boot_time()
        uptime = time.strftime("%H:%M:%S", time.gmtime(uptime_seconds))

        exec_mode = (
            "EXE (PyInstaller)" if getattr(sys, "frozen", False)
            else "Script (.py)"
        )

        info = [
            "+   Maquina   + : + ------------------------------- +",
            f"Usuario         : {usuario}",
            f"Maquina         : {hostname}",
            f"Sistema         : {sistema} {release}",
            f"Versao SO       : {version}",
            f"Arquitetura     : {arquitetura}",
            f"Processador     : {processador}",
            f"CPU (nucleos)   : {cpu_cores} fisicos / {cpu_threads} logicos",
            f"Memoria RAM     : {ram_total} GB",
            f"Boot Mode       : {boot_mode}",
            f"Uptime          : {uptime}",
            f"Iniciado em     : {inicio}",
            f"Log salvo como  : {os.path.basename(self.log_file)}",
            " ",
            "+   Software  + : + ------------------------------- +",
            "Aplicacao       : Sek Optimize",
            f"Versao          : {VERSION_SOFTWARE}",
            f"Python          : {python_ver}",
            f"Executavel      : {exec_mode}",
            f"Diretorio base  : {os.getcwd()}",
        ]

        self.log("")

        max_lines = max(len(APP_ASCII), len(info))
        for i in range(max_lines):
            left  = APP_ASCII[i] if i < len(APP_ASCII) else " " * 38
            right = info[i]      if i < len(info)      else ""
            self.log(f"{left:<38}   {right}")

        self.log("")