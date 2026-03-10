from config import *
from util.system_details import *


# Prefixo injetado em todo comando shell para forcar UTF-8 no console Windows.
# chcp 65001 muda o code page para UTF-8 antes de executar qualquer coisa.
# ">nul 2>&1" suprime a mensagem "Active code page: 65001" que o chcp imprime.
_CMD_UTF8_PREFIX = "chcp 65001 >nul 2>&1 & "


class App:
    def __init__(self):
        super().__init__()

        self.gui        = None
        self.start_time = datetime.now()
        self.log_file   = self._gerar_log_file()

        # Fila thread-safe: threads escrevem, GUI consome via polling (root.after).
        # Nunca escrever diretamente em widgets fora da thread principal.
        self.log_queue = queue.Queue()

        self._running_count = 0
        self._running_lock  = threading.Lock()

        # Lock de execucao serial: apenas um run_command por vez.
        self._exec_lock = threading.Lock()

        # Flag de alto nivel consultada antes de aceitar novas execucoes.
        self._is_running = False

        # show_fetch() e chamado por main.py apos set_gui() estar pronto.

    def set_gui(self, gui):
        self.gui = gui

    # ============================================================
    # LOG CENTRAL
    # ============================================================
    def _gerar_log_file(self):
        hostname  = socket.gethostname()
        data_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        pasta     = "logs"
        os.makedirs(pasta, exist_ok=True)
        return os.path.join(pasta, f"{hostname}-{data_hora}.log")

    def log(self, msg):
        timestamp = datetime.now().strftime("[%d/%m/%Y %H:%M:%S] ")
        texto     = timestamp + str(msg)
        self.log_queue.put(texto)
        # Arquivo de log sempre em UTF-8 para preservar acentos e caracteres especiais.
        try:
            with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(texto + "\n")
        except OSError:
            pass

    # ============================================================
    # HELPERS DE LOG  (prefixo define a cor na GUI)
    # ============================================================
    def log_title(self, title):
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
    # PROGRESS BAR  (chamadas via root.after para ser thread-safe)
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
    # DECODE DE SAIDA DO PROCESSO
    #
    # Prioridade de decodificacao:
    #   1. UTF-8  (apos chcp 65001, a maioria dos programas usa UTF-8)
    #   2. UTF-16 LE com/sem BOM  (SFC em algumas versoes do Windows)
    #   3. CP850 / CP437          (OEM legado)
    #   4. Latin-1                (fallback universal)
    # ============================================================
    def _decode(self, raw):
        # UTF-16 com BOM explicito
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            try:
                return raw.decode("utf-16", errors="replace")
            except Exception:
                pass

        # UTF-16 LE sem BOM: bytes pares tendem a ser zero para ASCII
        if len(raw) > 2 and len(raw) % 2 == 0 and raw[1:2] == b"\x00":
            try:
                return raw.decode("utf-16-le", errors="replace")
            except Exception:
                pass

        # Encodings ordenados por prioridade
        for enc in ("utf-8", "cp850", "cp437", "latin-1"):
            try:
                return raw.decode(enc, errors="strict")
            except (UnicodeDecodeError, LookupError):
                pass

        return raw.decode("latin-1", errors="replace")

    # ============================================================
    # LEITURA DE STDOUT COM SUPORTE A \r  (SFC, DISM, CHKDSK)
    #
    # Esses programas usam \r para atualizar a linha de progresso
    # sem emitir \n. O iterador padrao do Python so quebra em \n,
    # entao o buffer ficaria preso ate o processo encerrar.
    # Esta funcao le em chunks e divide nos dois separadores.
    # ============================================================
    def _read_lines(self, stream):
        buf = b""
        while True:
            chunk = stream.read(256)
            if not chunk:
                if buf.strip():
                    yield buf
                break
            buf += chunk
            while True:
                nl = buf.find(b"\n")
                cr = buf.find(b"\r")

                if nl == -1 and cr == -1:
                    break

                if   nl == -1:              pos, skip = cr, 1
                elif cr == -1:              pos, skip = nl, 1
                elif nl < cr:               pos, skip = nl, 1
                else:                       pos, skip = cr, 1

                line = buf[:pos]
                buf  = buf[pos + skip:]

                if line.strip():
                    yield line

    # ============================================================
    # EXECUCAO DE COMANDO SHELL
    #
    # Injeta o prefixo UTF-8 (chcp 65001) antes de cada comando.
    # Garante execucao serial via _exec_lock.
    # ============================================================
    def run_command(self, desc, cmd):
        with self._exec_lock:
            self.log_title(desc)
            self._progress_start(desc)
            try:
                # chcp 65001 forca UTF-8 no console antes do comando real
                full_cmd = _CMD_UTF8_PREFIX + cmd
                proc = subprocess.Popen(
                    full_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if sys.platform == "win32" else 0
                    ),
                )
                for raw in self._read_lines(proc.stdout):
                    line = self._decode(raw)
                    # Remove residuos de controle do terminal
                    line = line.replace("\r", "").replace("\x00", "").strip()
                    if line:
                        self.log(line)
                proc.wait()
            except Exception as e:
                self.log_error(str(e))
            finally:
                self._progress_stop()
                self.log_sep()
                self.log_ok("Finalizado.")
                self.log("")

    # ============================================================
    # EXECUCAO DE COMANDO DO TERMINAL DA GUI
    # ============================================================
    def run_custom_command(self, command):
        if self._is_running:
            self.log_warn("Aguarde a execucao atual terminar.")
            return

        def _run():
            self._is_running = True
            self._progress_start(command)
            self.log_title(f"Terminal > {command}")
            try:
                full_cmd = _CMD_UTF8_PREFIX + command
                proc = subprocess.Popen(
                    full_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if sys.platform == "win32" else 0
                    ),
                )
                for raw in self._read_lines(proc.stdout):
                    line = self._decode(raw).replace("\r", "").replace("\x00", "").strip()
                    if line:
                        self.log(line)
                proc.wait()
            except Exception as e:
                self.log_error(str(e))
            finally:
                self._is_running = False
                self._progress_stop()
                self.log("")

        threading.Thread(target=_run, daemon=True).start()

    # ============================================================
    # EXECUCAO DE ACOES (botoes / checkboxes)
    # ============================================================
    def execute_button(self, index):
        """Executa uma unica acao em thread de background."""
        if self._is_running:
            self.log_warn("Aguarde a execucao atual terminar antes de iniciar outra.")
            return

        action = ACTIONS.get(index)
        if not action:
            return

        handler_name = action["handler"]
        handler      = getattr(self, handler_name, None)

        def _run():
            self._is_running = True
            try:
                if handler:
                    handler()
                else:
                    cmd = COMMANDS.get(handler_name)
                    if cmd:
                        self.run_command(action["label"], cmd)
                    else:
                        self.log_error(f"Acao '{handler_name}' nao implementada.")
            finally:
                self._is_running = False

        threading.Thread(target=_run, daemon=True).start()

    def execute_sequence(self, indices):
        """
        Executa lista de acoes em sequencia dentro de uma unica thread.
        Nenhuma nova execucao e aceita enquanto a sequencia estiver ativa.
        """
        if self._is_running:
            self.log_warn("Aguarde a execucao atual terminar.")
            return

        def _run():
            self._is_running = True
            total = len(indices)
            self.log_title(f"SEQUENCIA INICIADA  ({total} acao(oes))")
            try:
                for pos, idx in enumerate(indices, 1):
                    action = ACTIONS.get(idx)
                    if not action:
                        continue
                    self.log_info(f"Passo {pos}/{total}: {action['label']}")
                    handler_name = action["handler"]
                    handler      = getattr(self, handler_name, None)
                    if handler:
                        handler()
                    else:
                        cmd = COMMANDS.get(handler_name)
                        if cmd:
                            self.run_command(action["label"], cmd)
            finally:
                self._is_running = False
                self.log_title("SEQUENCIA CONCLUIDA")

        threading.Thread(target=_run, daemon=True).start()

    # ============================================================
    # UTILITARIO: tamanho de pasta
    # ============================================================
    def get_folder_info(self, folder_path):
        total_size  = 0
        total_files = 0
        for root, dirs, files in os.walk(folder_path):
            total_files += len(files)
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except (OSError, PermissionError):
                    pass
        return round(total_size / (1024 ** 3), 2), total_files