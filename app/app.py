from config import *
from util.system_details import *


class App:
    def __init__(self):
        super().__init__()

        self.gui = None
        self.start_time = datetime.now()
        self.log_file = self._gerar_log_file()

        # Fila thread-safe: threads escrevem, GUI le via polling
        self.log_queue = queue.Queue()

        self._running_count = 0
        self._running_lock = threading.Lock()

        # Lock de execucao serial: impede que duas acoes rodem ao mesmo tempo
        self._exec_lock = threading.Lock()

        # show_fetch e chamado por main.py apos set_gui()

    def set_gui(self, gui):
        self.gui = gui

    # ============================================================
    # LOG CENTRAL
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
        self.log_queue.put(texto)
        try:
            with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(texto + "\n")
        except OSError:
            pass

    # ============================================================
    # HELPERS DE LOG
    # ============================================================
    def log_title(self, title):
        """Cabecalho padrao de secao com bordas duplas."""
        bar = "=" * 62
        self.log("")
        self.log(bar)
        self.log(f"  >> {title}")
        self.log(bar)

    def log_sep(self):
        self.log("-" * 62)

    def log_tree(self, title, lines):
        self.log("")
        self.log(f"[{title}]")
        for line in lines:
            self.log(line)

    def log_info(self, msg):
        self.log(f"[INFO] {msg}")

    def log_ok(self, msg):
        self.log(f"[OK] {msg}")

    def log_warn(self, msg):
        self.log(f"[AVISO] {msg}")

    def log_error(self, msg):
        self.log(f"[ERRO] {msg}")

    def log_block_raw(self, text):
        for line in text.splitlines():
            self.log(line)

    # ============================================================
    # PROGRESS (thread-safe via root.after)
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
        if self.gui and not active:
            self.gui.root.after(0, self.gui.progress_stop)

    # ============================================================
    # EXECUCAO DE COMANDOS SHELL
    # Usa _exec_lock para garantir execucao serial
    # ============================================================
    def _decode(self, raw):
        for enc in ("cp850", "utf-8", "latin-1"):
            try:
                return raw.decode(enc, errors="replace")
            except Exception:
                pass
        return raw.decode("latin-1", errors="replace")

    def run_command(self, desc, cmd):
        """Executa comando shell com cabecalho, progress e lock serial."""
        with self._exec_lock:
            self.log_title(desc)
            self._progress_start(desc)
            try:
                with subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                ) as proc:
                    for raw in proc.stdout:
                        line = self._decode(raw).replace("\r\n", "\n")
                        self.log(line.rstrip("\n"))
            except Exception as e:
                self.log_error(str(e))
            finally:
                self._progress_stop()
                self.log_sep()
                self.log_ok("Finalizado.")
                self.log("")

    def run_custom_command(self, command):
        """Executa comando digitado pelo usuario no terminal."""
        with self._exec_lock:
            self.log_title(f"Terminal > {command}")
            self._progress_start(command)
            try:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
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
                self.log("")

    # ============================================================
    # MAPEAMENTO DE ACOES
    # execute_button: dispara em thread unica (o lock garante serial)
    # execute_sequence: itera em thread unica, cada acao aguarda a anterior
    # ============================================================
    def execute_button(self, index):
        action = ACTIONS.get(index)
        if not action:
            return

        # Rejeita se ja ha algo em execucao
        if self._exec_lock.locked():
            self.log_warn("Aguarde a acao atual terminar antes de iniciar outra.")
            return

        handler_name = action["handler"]
        handler = getattr(self, handler_name, None)
        if handler:
            threading.Thread(target=handler, daemon=True).start()
            return
        cmd = COMMANDS.get(handler_name)
        if cmd:
            threading.Thread(
                target=self.run_command,
                args=(action["label"], cmd),
                daemon=True,
            ).start()
            return
        self.log_error(f"Acao '{handler_name}' nao implementada.")

    def execute_sequence(self, indices):
        """Executa lista de acoes em sequencia em thread unica."""
        if self._exec_lock.locked():
            self.log_warn("Aguarde a execucao atual terminar.")
            return

        def _run():
            total = len(indices)
            self.log_title(f"SEQUENCIA: {total} acao(oes) agendada(s)")
            for pos, idx in enumerate(indices, 1):
                action = ACTIONS.get(idx)
                if not action:
                    continue
                self.log_info(f"Passo {pos}/{total}: {action['label']}")
                handler_name = action["handler"]
                handler = getattr(self, handler_name, None)
                if handler:
                    handler()
                else:
                    cmd = COMMANDS.get(handler_name)
                    if cmd:
                        self.run_command(action["label"], cmd)
            self.log_title("SEQUENCIA CONCLUIDA")

        threading.Thread(target=_run, daemon=True).start()

    # ============================================================
    # UTILITARIOS
    # ============================================================
    def get_folder_info(self, folder_path):
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