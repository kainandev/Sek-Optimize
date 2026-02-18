from config import *

class FastFetch:
	def __init__(self):
		pass

		# ============================================
	# FAST FETCH
	# ============================================
	def on_gui_ready(self, gui):
		self.gui = gui
		self.show_fetch()

	def log_fetch(self, msg):
		if self.gui is None:
			return  # não mostra fetch fora da GUI

		self.gui.add_log(msg)

		with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
			f.write(msg + "\n")

	def log_tree(self, title, lines):
		self.log("")
		self.log(f"[{title}]")
		for line in lines:
			self.log(line)

	def log_title(self, title):
		self.log("")
		self.log("="*60)
		self.log(f"   {title}".center(60))
		self.log("="*60)

	def log_info(self, msg):
		self.log(f"[INFO] {msg}")

	def log_warn(self, msg):
		self.log(f"[ATENÇÂO] {msg}")

	def log_error(self, msg):
		self.log(f"[ERRO] {msg}")

	def log_block_raw(self, text):
		for line in text.splitlines():
			self.log(line)


	def show_fetch(self):
		inicio = self.start_time.strftime("%d/%m/%Y %H:%M:%S")

		usuario = getpass.getuser()
		hostname = socket.gethostname()

		sistema = platform.system()
		release = platform.release()
		version = platform.version()
		arquitetura = platform.machine()
		processador = platform.processor()
		python_ver = platform.python_version()

		cpu_cores = psutil.cpu_count(logical=False)
		cpu_threads = psutil.cpu_count(logical=True)

		ram_total = round(psutil.virtual_memory().total / (1024**3), 1)

		boot_mode = "UEFI" if os.path.exists("C:\\Windows\\System32\\SecureBoot.exe") else "Legacy"

		uptime_seconds = time.time() - psutil.boot_time()
		uptime = time.strftime("%H:%M:%S", time.gmtime(uptime_seconds))

		exec_mode = "EXE (PyInstaller)" if getattr(sys, "frozen", False) else "Script (.py)"

		info = [
			f"+   Máquina   + : + ------------------------------- +",
			f"Usuário         : {usuario}",
			f"Máquina         : {hostname}",
			f"Sistema         : {sistema} {release}",
			f"Versão SO       : {version}",
			f"Arquitetura     : {arquitetura}",
			f"Processador     : {processador}",
			f"CPU (núcleos)   : {cpu_cores} físicos / {cpu_threads} lógicos",
			f"Memória RAM     : {ram_total} GB",
			f"Boot Mode       : {boot_mode}",
			f"Uptime          : {uptime}",
			f"Iniciado em     : {inicio}",
			f"Log salvo como  : {os.path.basename(self.log_file)}",
			f" ",
			f"+   Software  + : + ------------------------------- +",
			f"Aplicação       : Sek Optimize",
			f"Versão          : {VERSION_SOFTWARE}",
			f"Python          : {python_ver}",
			f"Executável      : {exec_mode}",
			f"Diretório base  : {os.getcwd()}",
		]

		self.log_fetch("")  # linha em branco inicial

		max_lines = max(len(APP_ASCII), len(info))

		for i in range(max_lines):
			left = APP_ASCII[i] if i < len(APP_ASCII) else ""
			right = info[i] if i < len(info) else ""

			self.log_fetch(f"{left:<30}   {right}")

		self.log_fetch("")