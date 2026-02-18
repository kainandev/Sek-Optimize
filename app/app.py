from config import *
from app.fetch import FastFetch

class App(FastFetch):
    def __init__(self):
        super().__init__()

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