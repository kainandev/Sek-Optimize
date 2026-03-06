from config import *
from util.system_details import *


class App:
    def __init__(self):
        super().__init__()

        self.gui = None
        self.start_time = datetime.now()
        self.log_file = self._gerar_log_file()

        # Fila thread-safe: o log nunca chama widgets diretamente
        self.log_queue = queue.Queue()

        # Sinaliza quantas operacoes estao rodando (para a barra de progresso)
        self._running_count = 0
        self._running_lock = threading.Lock()
        # show_fetch e chamado externamente apos set_gui()

    def set_gui(self, gui):
        self.gui = gui

    # ============================================================
    # LOG CENTRAL
    # Escreve na fila e no arquivo. A GUI consome a fila via polling.
    # ============================================================
    def _gerar_log_file(self):
        hostname = socket.gethostname()
        data_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nome = f"{hostname}-{data_hora}.log"
        pasta = "logs"
        os.makedirs(pasta, exist_ok=True)
        return os.path.join(pasta, nome)

    def log(self, msg):
        timestamp = datetime.now().strftime("[%d/%m/%Y %H:%M:%S] ")
        texto = timestamp + str(msg)

        # Enfileira para a GUI consumir na thread principal
        self.log_queue.put(texto)

        # Salva no arquivo diretamente (thread-safe pois e IO sequencial)
        try:
            with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(texto + "\n")
        except OSError:
            pass

    # ============================================================
    # HELPERS DE LOG
    # ============================================================
    def log_title(self, title):
        self.log("")
        self.log("=" * 60)
        self.log(f"   {title}".center(60))
        self.log("=" * 60)

    def log_tree(self, title, lines):
        self.log("")
        self.log(f"[{title}]")
        for line in lines:
            self.log(line)

    def log_info(self, msg):
        self.log(f"[INFO] {msg}")

    def log_warn(self, msg):
        self.log(f"[ATENCAO] {msg}")

    def log_error(self, msg):
        self.log(f"[ERRO] {msg}")

    def log_block_raw(self, text):
        for line in text.splitlines():
            self.log(line)

    # ============================================================
    # PROGRESS: notifica a GUI de forma thread-safe via root.after
    # ============================================================
    def _progress_start(self, label="Executando..."):
        with self._running_lock:
            self._running_count += 1
        if self.gui:
            self.gui.root.after(0, lambda: self.gui.progress_start(label))

    def _progress_stop(self):
        with self._running_lock:
            self._running_count -= 1
            active = self._running_count > 0
        if self.gui:
            if not active:
                self.gui.root.after(0, self.gui.progress_stop)

    # ============================================================
    # EXECUCAO DE COMANDO SHELL
    # ============================================================
    def _decode(self, raw):
        for enc in ("cp850", "utf-8", "latin-1"):
            try:
                return raw.decode(enc, errors="replace")
            except Exception:
                pass
        return raw.decode("latin-1", errors="replace")

    def run_command(self, desc, cmd):
        """Executa um comando shell e transmite cada linha para o log."""
        self.log_title(desc)
        self._progress_start(desc)
        try:
            with subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            ) as proc:
                for raw in proc.stdout:
                    line = self._decode(raw).replace("\r\n", "\n")
                    self.log(line.rstrip("\n"))
        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()
            self.log("")
            self.log_info("Finalizado.")
            self.log("")

    # ============================================================
    # EXECUCAO A PARTIR DO TERMINAL DA GUI
    # ============================================================
    def run_custom_command(self, command):
        self.log(f"> {command}")
        self._progress_start(command)
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            for raw in proc.stdout:
                line = self._decode(raw).rstrip("\r\n")
                if line:
                    self.log(line)
            proc.wait()
        except Exception as e:
            self.log_error(str(e))
        finally:
            self._progress_stop()

    # ============================================================
    # MAPEAMENTO DOS BOTOES / ACOES
    # ============================================================
    def execute_button(self, index):
        action = ACTIONS.get(index)
        if not action:
            return

        handler_name = action["handler"]

        # Verifica se existe metodo Python na classe
        handler = getattr(self, handler_name, None)
        if handler:
            threading.Thread(target=handler, daemon=True).start()
            return

        # Verifica se existe comando shell direto no COMMANDS
        cmd = COMMANDS.get(handler_name)
        if cmd:
            label = action["label"]
            threading.Thread(
                target=self.run_command,
                args=(label, cmd),
                daemon=True
            ).start()
            return

        self.log_error(f"Acao '{handler_name}' nao implementada.")

    def execute_sequence(self, indices):
        """Executa uma lista de indices de acoes em sequencia, em thread unica."""
        def _run():
            for idx in indices:
                action = ACTIONS.get(idx)
                if not action:
                    continue
                handler_name = action["handler"]
                handler = getattr(self, handler_name, None)
                if handler:
                    handler()
                else:
                    cmd = COMMANDS.get(handler_name)
                    if cmd:
                        self.run_command(action["label"], cmd)
        threading.Thread(target=_run, daemon=True).start()

    # ============================================================
    # UTILITARIOS
    # ============================================================
    def get_folder_info(self, folder_path):
        """Retorna (tamanho em GB, quantidade de arquivos) de uma pasta."""
        total_size = 0
        total_files = 0
        for root, dirs, files in os.walk(folder_path):
            total_files += len(files)
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    total_size += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass
        return round(total_size / (1024 ** 3), 2), total_files