from app.app import *

# ==========================================
# RESOURCE PATH (PYINSTALLER)
# ==========================================
def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

icon_path = resource_path("icon.ico")

# ==========================================
# GUI
# ==========================================
class GUI:

    def __init__(self, root, app):
        self.root = root
        self.app = app

        self.autocomplete_index = 0
        self.selected_index = None

        self.root.title("Sek Optimize")
        self.root.geometry("1400x700")
        self.root.configure(bg="#1e1e1e")
        self.root.iconbitmap(icon_path)

        self._build_layout()
        self._build_tabs()

    # ----------------------------------------------------------
    # LAYOUT PRINCIPAL
    # ----------------------------------------------------------
    def _build_layout(self):

        self.bg_main = "#1e1e1e"
        self.bg_frame = "#2b2b2b"
        self.bg_button = "#3a3a3a"
        self.fg_text = "#e0e0e0"

        # ============================
        # FRAME ESQUERDO
        # ============================
        self.left_container = tk.Frame(
            self.root,
            bg=self.bg_main,
            width=500
        )
        self.left_container.pack(
            side=tk.LEFT,
            fill=tk.Y,
            expand=False,
            padx=5,
            pady=5
        )
        self.left_container.pack_propagate(False)


        top_left = tk.Frame(self.left_container, bg=self.bg_main)
        top_left.pack(fill=tk.X)

        bottom_left = tk.Frame(self.left_container, bg=self.bg_main)
        bottom_left.pack(fill=tk.X, pady=(10, 0))

        # ============================
        # NOTEBOOK
        # ============================
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=self.bg_main, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=self.bg_frame,
                        foreground=self.fg_text,
                        padding=[5, 2],
                        font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", "#3d3d3d")])

        self.tab_control = ttk.Notebook(top_left)
        self.tab_control.pack(fill=tk.X, expand=False)

        # ============================
        # DESCRIÇÃO
        # ============================
        desc_frame = tk.LabelFrame(
            bottom_left,
            text="Descrição da Ação",
            fg="white",
            bg="#2d2d2d"
        )
        desc_frame.pack(fill="x")

        self.desc_text = tk.Text(
            desc_frame,
            height=10,
            bg="#1e1e1e",
            fg="white",
            state="disabled",
            wrap="word"
        )
        self.desc_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.execute_btn = tk.Button(
            desc_frame,
            text="Executar",
            state=tk.DISABLED,
            command=self._execute_selected,
            width=20
        )
        self.execute_btn.pack(pady=3)

        # ============================
        # LOGS
        # ============================
        right_frame = tk.LabelFrame(
            self.root,
            text="Logs",
            fg=self.fg_text,
            bg=self.bg_frame
        )
        right_frame.pack(
            side=tk.RIGHT,
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=10
        )

        self.log_box = scrolledtext.ScrolledText(
            right_frame,
            bg="black",
            fg="#00ff00",
            font=("Consolas", 9),
            state="disabled"
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)

        self.log_box.tag_configure(
            "tight",
            spacing1=0,
            spacing2=-2,
            spacing3=0
        )

        # ============================
        # TERMINAL
        # ============================
        cmd_frame = tk.Frame(right_frame, bg=self.bg_frame)
        cmd_frame.pack(fill=tk.X, pady=(5, 0))

        self.cmd_entry = tk.Entry(
            cmd_frame,
            bg="#1e1e1e",
            fg="#00ff00",
            font=("Consolas", 10),
            relief="flat"
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        self.placeholder = "Digite um comando (ex: ipconfig)"
        self._set_placeholder()

        # BINDS (AGORA NO LUGAR CORRETO)
        self.cmd_entry.bind("<FocusIn>", self._clear_placeholder)
        self.cmd_entry.bind("<FocusOut>", self._restore_placeholder)
        self.cmd_entry.bind("<Return>", self._send_command)
        self.cmd_entry.bind("<Tab>", self._autocomplete)

        tk.Button(
            cmd_frame,
            text="Enviar",
            bg=self.bg_button,
            fg="white",
            width=10,
            command=self._send_command
        ).pack(side=tk.RIGHT, padx=5, pady=5)




    # ----------------------------------------------------------
    # TABS
    # ----------------------------------------------------------
    def _build_tabs(self):
        tabs = defaultdict(list)

        for idx, cfg in ACTIONS.items():
            tabs[cfg["tab"]].append(idx)

        self.labels = {i: cfg["label"] for i, cfg in ACTIONS.items()}
        self.danger_indices = {i for i, cfg in ACTIONS.items() if cfg["danger"]}

        for tab, indices in tabs.items():
            frame = tk.Frame(self.tab_control, bg=self.bg_main)
            self.tab_control.add(frame, text=tab)

            for idx in sorted(indices):
                tk.Button(
                    frame,
                    text=self.labels[idx],
                    anchor="w",
                    width=35,
                    command=lambda i=idx: self._select_button(i)
                ).pack(fill="x", pady=1, padx=5)

    # ----------------------------------------------------------
    # AÇÕES
    # ----------------------------------------------------------
    def _select_button(self, index):
        self.selected_index = index

        self.desc_text.config(state="normal")
        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert(tk.END, ACTIONS[index]["description"])
        self.desc_text.config(state="disabled")

        self.execute_btn.config(state=tk.NORMAL)

    def _execute_selected(self):
        if self.selected_index is None:
            return
        self.app.execute_button(self.selected_index)
        self.execute_btn.config(state=tk.DISABLED)

    # ----------------------------------------------------------
    # TERMINAL
    # ----------------------------------------------------------
    def _send_command(self, event=None):
        cmd = self.cmd_entry.get().strip()

        if not cmd or cmd == self.placeholder:
            return

        self.add_log(f"> {cmd}")
        self.cmd_entry.delete(0, tk.END)
        self.app.run_custom_command(cmd)

    def _autocomplete(self, event):
        text = self.cmd_entry.get().strip()

        if not text or text == self.placeholder:
            return "break"

        matches = [c for c in AUTOCOMPLETE_COMMANDS if c.startswith(text)]
        if not matches:
            return "break"

        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.insert(0, matches[self.autocomplete_index % len(matches)])
        self.autocomplete_index += 1
        return "break"

    # ----------------------------------------------------------
    # PLACEHOLDER
    # ----------------------------------------------------------
    def _set_placeholder(self):
        self.cmd_entry.insert(0, self.placeholder)
        self.cmd_entry.config(fg="#777777")

    def _clear_placeholder(self, _):
        if self.cmd_entry.get() == self.placeholder:
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.config(fg="#00ff00")

    def _restore_placeholder(self, _):
        if not self.cmd_entry.get():
            self._set_placeholder()

    # ----------------------------------------------------------
    # LOG
    # ----------------------------------------------------------
    def add_log(self, text):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\n", "tight")
        self.log_box.see("end")
        self.log_box.config(state="disabled")
