import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import json
import os
from config import ACTIONS, AUTOCOMPLETE_COMMANDS, APP_ASCII, VERSION_SOFTWARE, GROUPS_FILE
from collections import defaultdict

# ============================================================
# PALETA DE CORES
# ============================================================
C_BG        = "#18181f"   # fundo principal
C_SIDEBAR   = "#101018"   # barra lateral
C_CARD      = "#22222e"   # cartoes / paineis
C_CARD2     = "#1c1c28"   # cartao secundario
C_HOVER     = "#2a2a3a"   # hover em itens
C_SEL       = "#1e3050"   # item selecionado/marcado
C_BORDER    = "#2e2e3e"   # bordas sutis
C_ACCENT    = "#4a80ff"   # azul primario
C_ACCENT2   = "#3060cc"   # azul escuro (hover do botao)
C_TEXT      = "#d8d8e8"   # texto principal
C_DIM       = "#6868a0"   # texto secundario/apagado
C_SUCCESS   = "#48d890"   # verde OK
C_WARNING   = "#f0a040"   # laranja aviso
C_DANGER    = "#e85050"   # vermelho perigo
C_LOG_BG    = "#0c0c14"   # fundo do terminal
C_LOG_FG    = "#38d060"   # texto verde do terminal

FONT_TITLE  = ("Segoe UI", 11, "bold")
FONT_NORM   = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_MONO   = ("Consolas", 9)

# Prefixos de checkbox no texto da arvore
CHK_OFF = "[ ]"
CHK_ON  = "[X]"


def resource_path(relative_path):
    """Compatibilidade com PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


import sys


# ============================================================
# GUI PRINCIPAL
# ============================================================
class GUI:

    def __init__(self, root, app):
        self.root = root
        self.app  = app

        self.autocomplete_index = 0

        # estado dos checkboxes: action_idx -> bool
        self.checked = {}

        # mapa: tree item id -> action_idx
        self.tree_items = {}

        self._setup_window()
        self._apply_theme()
        self._build_header()
        self._build_body()
        self._build_statusbar()

        # Inicia polling da fila de log (nao trava a GUI)
        self._poll_log_queue()

    # ============================================================
    # JANELA
    # ============================================================
    def _setup_window(self):
        self.root.title(f"Sek Optimize  v{VERSION_SOFTWARE}")
        self.root.geometry("1300x720")
        self.root.minsize(1000, 600)
        self.root.configure(bg=C_BG)

        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

    # ============================================================
    # TEMA TTK GLOBAL
    # ============================================================
    def _apply_theme(self):
        style = ttk.Style(self.root)
        style.theme_use("default")

        # --- Treeview ---
        style.configure(
            "App.Treeview",
            background=C_CARD,
            foreground=C_TEXT,
            fieldbackground=C_CARD,
            rowheight=26,
            font=FONT_NORM,
            borderwidth=0,
        )
        style.configure(
            "App.Treeview.Heading",
            background=C_CARD2,
            foreground=C_DIM,
            relief="flat",
            font=FONT_SMALL,
        )
        style.map(
            "App.Treeview",
            background=[("selected", C_SEL)],
            foreground=[("selected", C_TEXT)],
        )

        # --- Scrollbar fina ---
        style.configure(
            "App.Vertical.TScrollbar",
            troughcolor=C_CARD,
            background=C_BORDER,
            borderwidth=0,
            arrowsize=10,
        )

        # --- Progressbar ---
        style.configure(
            "App.Horizontal.TProgressbar",
            troughcolor=C_CARD2,
            background=C_ACCENT,
            borderwidth=0,
        )

        # --- Separador ---
        style.configure("TSeparator", background=C_BORDER)

    # ============================================================
    # HEADER
    # ============================================================
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C_SIDEBAR, height=46)
        hdr.pack(side=tk.TOP, fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(
            hdr,
            text="Sek Optimize",
            bg=C_SIDEBAR,
            fg=C_ACCENT,
            font=("Segoe UI", 13, "bold"),
        ).pack(side=tk.LEFT, padx=16, pady=10)

        tk.Label(
            hdr,
            text=f"v{VERSION_SOFTWARE}",
            bg=C_SIDEBAR,
            fg=C_DIM,
            font=FONT_SMALL,
        ).pack(side=tk.LEFT, pady=10)

        # Separador horizontal abaixo do header
        tk.Frame(self.root, bg=C_BORDER, height=1).pack(fill=tk.X)

    # ============================================================
    # CORPO PRINCIPAL
    # ============================================================
    def _build_body(self):
        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True)

        self._build_sidebar(body)
        self._build_content(body)
        self._build_log_panel(body)

    # ============================================================
    # SIDEBAR
    # ============================================================
    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=C_SIDEBAR, width=158)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        sb.pack_propagate(False)

        # Separador vertical
        tk.Frame(parent, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        self._sidebar_buttons = {}
        self._active_view = tk.StringVar(value="acoes")

        nav_items = [
            ("acoes",  "Acoes"),
            ("grupos", "Grupos"),
        ]

        tk.Frame(sb, bg=C_SIDEBAR, height=12).pack()

        for key, label in nav_items:
            btn = tk.Label(
                sb,
                text=label,
                bg=C_SIDEBAR,
                fg=C_TEXT,
                font=FONT_NORM,
                anchor="w",
                padx=18,
                pady=9,
                cursor="hand2",
            )
            btn.pack(fill=tk.X)
            btn.bind("<Button-1>", lambda e, k=key: self._switch_view(k))
            btn.bind("<Enter>",    lambda e, b=btn: b.config(bg=C_HOVER))
            btn.bind("<Leave>",    lambda e, b=btn, k=key: b.config(
                bg=C_ACCENT2 if self._active_view.get() == k else C_SIDEBAR
            ))
            self._sidebar_buttons[key] = btn

        self._update_sidebar_highlight("acoes")

    def _update_sidebar_highlight(self, active_key):
        for key, btn in self._sidebar_buttons.items():
            btn.config(bg=C_ACCENT2 if key == active_key else C_SIDEBAR)

    # ============================================================
    # AREA DE CONTEUDO (troca entre views)
    # ============================================================
    def _build_content(self, parent):
        self.content_frame = tk.Frame(parent, bg=C_BG, width=430)
        self.content_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.content_frame.pack_propagate(False)

        # Separador vertical
        tk.Frame(parent, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Cria ambas as views e exibe so a ativa
        self._view_acoes  = tk.Frame(self.content_frame, bg=C_BG)
        self._view_grupos = tk.Frame(self.content_frame, bg=C_BG)

        self._build_view_acoes(self._view_acoes)
        self._build_view_grupos(self._view_grupos)

        self._switch_view("acoes")

    def _switch_view(self, key):
        self._active_view.set(key)
        self._update_sidebar_highlight(key)
        self._view_acoes.pack_forget()
        self._view_grupos.pack_forget()
        if key == "acoes":
            self._view_acoes.pack(fill=tk.BOTH, expand=True)
        else:
            self._view_grupos.pack(fill=tk.BOTH, expand=True)
            self._refresh_groups_list()

    # ============================================================
    # VIEW: ACOES (arvore com checkboxes)
    # ============================================================
    def _build_view_acoes(self, parent):
        # -- Toolbar --
        toolbar = tk.Frame(parent, bg=C_CARD2, height=42)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        self._make_flat_btn(
            toolbar, "Selecionar Tudo", self._check_all
        ).pack(side=tk.LEFT, padx=(8, 3), pady=8)

        self._make_flat_btn(
            toolbar, "Limpar", self._uncheck_all
        ).pack(side=tk.LEFT, padx=3, pady=8)

        self.btn_run = self._make_accent_btn(
            toolbar, "Executar Selecionados", self._execute_checked
        )
        self.btn_run.pack(side=tk.RIGHT, padx=8, pady=8)

        # Separador
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)

        # -- Descricao da acao selecionada --
        desc_frame = tk.Frame(parent, bg=C_CARD2, height=72)
        desc_frame.pack(fill=tk.X)
        desc_frame.pack_propagate(False)

        self.desc_label = tk.Label(
            desc_frame,
            text="Selecione uma acao na lista abaixo para ver a descricao.",
            bg=C_CARD2,
            fg=C_DIM,
            font=FONT_SMALL,
            anchor="nw",
            justify="left",
            wraplength=400,
            padx=10,
            pady=8,
        )
        self.desc_label.pack(fill=tk.BOTH, expand=True)

        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)

        # -- Treeview --
        tree_frame = tk.Frame(parent, bg=C_CARD)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_frame,
            style="App.Treeview",
            selectmode="none",
            show="tree",
        )
        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
            style="App.Vertical.TScrollbar",
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.tag_configure("group",   foreground=C_ACCENT,   font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("normal",  foreground=C_TEXT)
        self.tree.tag_configure("danger",  foreground=C_WARNING)
        self.tree.tag_configure("checked", foreground=C_SUCCESS)

        self.tree.bind("<Button-1>",        self._on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self._populate_tree()

    def _populate_tree(self):
        """Monta a arvore de acoes agrupadas por aba."""
        self.tree.delete(*self.tree.get_children())
        self.tree_items.clear()
        self.checked.clear()

        groups = defaultdict(list)
        for idx, action in ACTIONS.items():
            groups[action["tab"]].append(idx)

        for group_name in sorted(groups.keys()):
            indices = sorted(groups[group_name])
            group_id = self.tree.insert(
                "", "end",
                text=f"  {group_name}",
                open=True,
                tags=("group",),
            )
            for idx in indices:
                action = ACTIONS[idx]
                label  = f"  {CHK_OFF}  {action['label']}"
                tag    = "danger" if action["danger"] else "normal"
                item_id = self.tree.insert(
                    group_id, "end",
                    text=label,
                    tags=(tag,),
                )
                self.tree_items[item_id] = idx
                self.checked[idx] = False

    def _on_tree_click(self, event):
        """Alterna checkbox ao clicar em um item folha."""
        item = self.tree.identify_row(event.y)
        if not item or not self.tree.parent(item):
            # Clique no grupo: abre/fecha
            return
        self._toggle_item(item)

    def _on_tree_select(self, event):
        """Atualiza descricao ao selecionar item."""
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        if item not in self.tree_items:
            return
        idx    = self.tree_items[item]
        action = ACTIONS.get(idx, {})
        desc   = action.get("description", "")
        danger = action.get("danger", False)
        color  = C_WARNING if danger else C_TEXT
        self.desc_label.config(text=desc, fg=color)

    def _toggle_item(self, item_id):
        """Marca ou desmarca um item e atualiza o texto e a cor."""
        if item_id not in self.tree_items:
            return
        idx = self.tree_items[item_id]
        new_state = not self.checked.get(idx, False)
        self.checked[idx] = new_state

        current_text = self.tree.item(item_id, "text")
        if new_state:
            new_text = current_text.replace(CHK_OFF, CHK_ON, 1)
            new_tag  = "checked"
        else:
            new_text = current_text.replace(CHK_ON, CHK_OFF, 1)
            action   = ACTIONS.get(idx, {})
            new_tag  = "danger" if action.get("danger") else "normal"

        self.tree.item(item_id, text=new_text, tags=(new_tag,))

    def _check_all(self):
        for item_id, idx in self.tree_items.items():
            self.checked[idx] = False
            self._toggle_item(item_id)

    def _uncheck_all(self):
        for item_id, idx in self.tree_items.items():
            self.checked[idx] = True
            self._toggle_item(item_id)

    def _execute_checked(self):
        selected = [idx for idx, state in self.checked.items() if state]
        if not selected:
            messagebox.showinfo("Nenhuma acao", "Selecione ao menos uma acao antes de executar.")
            return
        # Ordena pela ordem definida em ACTIONS para execucao previsivel
        selected.sort()
        self.app.execute_sequence(selected)

    # ============================================================
    # VIEW: GRUPOS (macros)
    # ============================================================
    def _build_view_grupos(self, parent):
        # Carrega grupos salvos
        self._groups = self._load_groups()

        # -- Toolbar --
        toolbar = tk.Frame(parent, bg=C_CARD2, height=42)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        self._make_flat_btn(
            toolbar, "Novo Grupo", self._new_group
        ).pack(side=tk.LEFT, padx=(8, 3), pady=8)

        self._make_flat_btn(
            toolbar, "Excluir", self._delete_group
        ).pack(side=tk.LEFT, padx=3, pady=8)

        self._make_accent_btn(
            toolbar, "Executar Grupo", self._run_group
        ).pack(side=tk.RIGHT, padx=8, pady=8)

        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)

        # -- Painel dividido: lista de grupos (esq) | editor (dir) --
        pane = tk.Frame(parent, bg=C_BG)
        pane.pack(fill=tk.BOTH, expand=True)

        # Lista de grupos
        list_frame = tk.Frame(pane, bg=C_CARD2, width=170)
        list_frame.pack(side=tk.LEFT, fill=tk.Y)
        list_frame.pack_propagate(False)

        tk.Label(
            list_frame,
            text="Grupos salvos",
            bg=C_CARD2,
            fg=C_DIM,
            font=FONT_SMALL,
            anchor="w",
            padx=10,
            pady=6,
        ).pack(fill=tk.X)

        tk.Frame(list_frame, bg=C_BORDER, height=1).pack(fill=tk.X)

        self.groups_listbox = tk.Listbox(
            list_frame,
            bg=C_CARD2,
            fg=C_TEXT,
            selectbackground=C_SEL,
            selectforeground=C_TEXT,
            font=FONT_NORM,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.groups_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.groups_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        # Separador vertical
        tk.Frame(pane, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Editor de grupo
        edit_outer = tk.Frame(pane, bg=C_BG)
        edit_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Nome do grupo
        name_frame = tk.Frame(edit_outer, bg=C_CARD2, height=40)
        name_frame.pack(fill=tk.X)
        name_frame.pack_propagate(False)

        tk.Label(
            name_frame,
            text="Nome:",
            bg=C_CARD2,
            fg=C_DIM,
            font=FONT_SMALL,
            padx=10,
        ).pack(side=tk.LEFT, pady=8)

        self.group_name_var = tk.StringVar()
        self.group_name_entry = tk.Entry(
            name_frame,
            textvariable=self.group_name_var,
            bg=C_CARD,
            fg=C_TEXT,
            insertbackground=C_TEXT,
            relief="flat",
            font=FONT_NORM,
        )
        self.group_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=6)

        self._make_flat_btn(
            name_frame, "Salvar", self._save_group
        ).pack(side=tk.RIGHT, padx=8, pady=6)

        tk.Frame(edit_outer, bg=C_BORDER, height=1).pack(fill=tk.X)

        tk.Label(
            edit_outer,
            text="Acoes do grupo  (marque as que devem fazer parte)",
            bg=C_BG,
            fg=C_DIM,
            font=FONT_SMALL,
            anchor="w",
            padx=10,
            pady=6,
        ).pack(fill=tk.X)

        # Arvore de acoes para o grupo (semelhante a view acoes)
        gtree_frame = tk.Frame(edit_outer, bg=C_CARD)
        gtree_frame.pack(fill=tk.BOTH, expand=True)

        self.group_tree = ttk.Treeview(
            gtree_frame,
            style="App.Treeview",
            selectmode="none",
            show="tree",
        )
        gscroll = ttk.Scrollbar(
            gtree_frame,
            orient="vertical",
            command=self.group_tree.yview,
            style="App.Vertical.TScrollbar",
        )
        self.group_tree.configure(yscrollcommand=gscroll.set)
        gscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.group_tree.pack(fill=tk.BOTH, expand=True)

        self.group_tree.tag_configure("group",   foreground=C_ACCENT, font=("Segoe UI", 10, "bold"))
        self.group_tree.tag_configure("normal",  foreground=C_TEXT)
        self.group_tree.tag_configure("danger",  foreground=C_WARNING)
        self.group_tree.tag_configure("checked", foreground=C_SUCCESS)

        # mapa: tree item id -> action_idx (para o editor de grupo)
        self.group_tree_items  = {}
        self.group_checked     = {}

        self._populate_group_tree()

        self.group_tree.bind("<Button-1>", self._on_group_tree_click)

    def _populate_group_tree(self, preset_indices=None):
        """Monta a arvore do editor de grupo."""
        preset = set(preset_indices or [])
        self.group_tree.delete(*self.group_tree.get_children())
        self.group_tree_items.clear()
        self.group_checked.clear()

        groups = defaultdict(list)
        for idx, action in ACTIONS.items():
            groups[action["tab"]].append(idx)

        for group_name in sorted(groups.keys()):
            indices = sorted(groups[group_name])
            gid = self.group_tree.insert(
                "", "end",
                text=f"  {group_name}",
                open=True,
                tags=("group",),
            )
            for idx in indices:
                action = ACTIONS[idx]
                checked = idx in preset
                prefix  = CHK_ON if checked else CHK_OFF
                label   = f"  {prefix}  {action['label']}"
                tag     = "checked" if checked else ("danger" if action["danger"] else "normal")
                item_id = self.group_tree.insert(gid, "end", text=label, tags=(tag,))
                self.group_tree_items[item_id] = idx
                self.group_checked[idx] = checked

    def _on_group_tree_click(self, event):
        item = self.group_tree.identify_row(event.y)
        if not item or not self.group_tree.parent(item):
            return
        self._toggle_group_tree_item(item)

    def _toggle_group_tree_item(self, item_id):
        if item_id not in self.group_tree_items:
            return
        idx       = self.group_tree_items[item_id]
        new_state = not self.group_checked.get(idx, False)
        self.group_checked[idx] = new_state

        current_text = self.group_tree.item(item_id, "text")
        if new_state:
            new_text = current_text.replace(CHK_OFF, CHK_ON, 1)
            new_tag  = "checked"
        else:
            new_text = current_text.replace(CHK_ON, CHK_OFF, 1)
            action   = ACTIONS.get(idx, {})
            new_tag  = "danger" if action.get("danger") else "normal"

        self.group_tree.item(item_id, text=new_text, tags=(new_tag,))

    def _on_group_select(self, event):
        """Carrega o grupo selecionado no editor."""
        sel = self.groups_listbox.curselection()
        if not sel:
            return
        name = self.groups_listbox.get(sel[0])
        group = self._groups.get(name, {})
        self.group_name_var.set(name)
        self._populate_group_tree(preset_indices=group.get("actions", []))

    def _new_group(self):
        """Limpa o editor para criacao de novo grupo."""
        self.groups_listbox.selection_clear(0, tk.END)
        self.group_name_var.set("")
        self._populate_group_tree()
        self.group_name_entry.focus_set()

    def _save_group(self):
        name = self.group_name_var.get().strip()
        if not name:
            messagebox.showwarning("Nome vazio", "Informe um nome para o grupo.")
            return
        selected = sorted([idx for idx, state in self.group_checked.items() if state])
        if not selected:
            messagebox.showwarning("Grupo vazio", "Selecione ao menos uma acao para o grupo.")
            return
        self._groups[name] = {"actions": selected}
        self._save_groups()
        self._refresh_groups_list()
        messagebox.showinfo("Salvo", f"Grupo '{name}' salvo com {len(selected)} acao(oes).")

    def _delete_group(self):
        sel = self.groups_listbox.curselection()
        if not sel:
            messagebox.showinfo("Nenhum grupo", "Selecione um grupo na lista para excluir.")
            return
        name = self.groups_listbox.get(sel[0])
        if messagebox.askyesno("Excluir grupo", f"Excluir o grupo '{name}'?"):
            self._groups.pop(name, None)
            self._save_groups()
            self._refresh_groups_list()
            self._new_group()

    def _run_group(self):
        sel = self.groups_listbox.curselection()
        if not sel:
            messagebox.showinfo("Nenhum grupo", "Selecione um grupo na lista para executar.")
            return
        name    = self.groups_listbox.get(sel[0])
        group   = self._groups.get(name, {})
        indices = group.get("actions", [])
        if not indices:
            messagebox.showinfo("Grupo vazio", "Este grupo nao possui acoes.")
            return
        self.app.execute_sequence(indices)

    def _refresh_groups_list(self):
        self.groups_listbox.delete(0, tk.END)
        for name in sorted(self._groups.keys()):
            self.groups_listbox.insert(tk.END, name)

    # ============================================================
    # PERSISTENCIA DE GRUPOS
    # ============================================================
    def _load_groups(self):
        if os.path.exists(GROUPS_FILE):
            try:
                with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_groups(self):
        try:
            with open(GROUPS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._groups, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============================================================
    # PAINEL DE LOG (lado direito)
    # ============================================================
    def _build_log_panel(self, parent):
        log_outer = tk.Frame(parent, bg=C_BG)
        log_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=0)

        # Cabecalho do log
        log_hdr = tk.Frame(log_outer, bg=C_CARD2, height=36)
        log_hdr.pack(fill=tk.X)
        log_hdr.pack_propagate(False)

        tk.Label(
            log_hdr,
            text="Log de Execucao",
            bg=C_CARD2,
            fg=C_DIM,
            font=FONT_SMALL,
            padx=10,
        ).pack(side=tk.LEFT, pady=8)

        self._make_flat_btn(
            log_hdr, "Limpar", self._clear_log
        ).pack(side=tk.RIGHT, padx=8, pady=6)

        tk.Frame(log_outer, bg=C_BORDER, height=1).pack(fill=tk.X)

        # Caixa de log
        self.log_box = scrolledtext.ScrolledText(
            log_outer,
            bg=C_LOG_BG,
            fg=C_LOG_FG,
            font=FONT_MONO,
            state="disabled",
            relief="flat",
            borderwidth=0,
            wrap="none",
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)
        self.log_box.tag_configure("tight", spacing1=0, spacing2=-2, spacing3=0)

        # Configuracoes de cor por prefixo
        self.log_box.tag_configure("info",  foreground="#60a8ff")
        self.log_box.tag_configure("warn",  foreground=C_WARNING)
        self.log_box.tag_configure("error", foreground=C_DANGER)

        tk.Frame(log_outer, bg=C_BORDER, height=1).pack(fill=tk.X)

        # Terminal de comandos
        cmd_frame = tk.Frame(log_outer, bg=C_CARD2, height=36)
        cmd_frame.pack(fill=tk.X)
        cmd_frame.pack_propagate(False)

        self._PLACEHOLDER = "Digite um comando (ex: ipconfig)"

        self.cmd_entry = tk.Entry(
            cmd_frame,
            bg=C_LOG_BG,
            fg=C_DIM,
            insertbackground=C_LOG_FG,
            font=FONT_MONO,
            relief="flat",
            borderwidth=0,
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)
        self.cmd_entry.insert(0, self._PLACEHOLDER)

        self.cmd_entry.bind("<FocusIn>",  self._cmd_focus_in)
        self.cmd_entry.bind("<FocusOut>", self._cmd_focus_out)
        self.cmd_entry.bind("<Return>",   self._send_command)
        self.cmd_entry.bind("<Tab>",      self._autocomplete)

        self._make_flat_btn(
            cmd_frame, "Enviar", self._send_command
        ).pack(side=tk.RIGHT, padx=8, pady=6)

    def _clear_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.config(state="disabled")

    # ============================================================
    # STATUS BAR + BARRA DE PROGRESSO
    # ============================================================
    def _build_statusbar(self):
        tk.Frame(self.root, bg=C_BORDER, height=1).pack(fill=tk.X)

        bar = tk.Frame(self.root, bg=C_CARD2, height=28)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        self.status_label = tk.Label(
            bar,
            text="Pronto",
            bg=C_CARD2,
            fg=C_DIM,
            font=FONT_SMALL,
            padx=10,
        )
        self.status_label.pack(side=tk.LEFT, pady=4)

        self.progress = ttk.Progressbar(
            bar,
            style="App.Horizontal.TProgressbar",
            mode="indeterminate",
            length=160,
        )
        self.progress.pack(side=tk.RIGHT, padx=10, pady=5)

    def progress_start(self, label="Executando..."):
        self.status_label.config(text=label, fg=C_ACCENT)
        self.progress.start(12)

    def progress_stop(self):
        self.progress.stop()
        self.status_label.config(text="Pronto", fg=C_DIM)

    # ============================================================
    # POLLING DA FILA DE LOG (substitui add_log direto por thread)
    # ============================================================
    def _poll_log_queue(self):
        try:
            while True:
                msg = self.app.log_queue.get_nowait()
                self._append_log(msg)
        except Exception:
            pass
        # Reagenda a cada 40 ms (nao trava a GUI)
        self.root.after(40, self._poll_log_queue)

    def _append_log(self, text):
        self.log_box.config(state="normal")

        # Coloriza linhas especiais
        tag = "tight"
        lower = text.lower()
        if "[info]" in lower:
            tag = "info"
        elif "[atencao]" in lower:
            tag = "warn"
        elif "[erro]" in lower:
            tag = "error"

        self.log_box.insert("end", text + "\n", tag)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    # Mantido por compatibilidade caso haja chamadas diretas
    def add_log(self, text):
        self._append_log(text)

    # ============================================================
    # TERMINAL DE COMANDOS
    # ============================================================
    def _cmd_focus_in(self, _event):
        if self.cmd_entry.get() == self._PLACEHOLDER:
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.config(fg=C_LOG_FG)

    def _cmd_focus_out(self, _event):
        if not self.cmd_entry.get():
            self.cmd_entry.insert(0, self._PLACEHOLDER)
            self.cmd_entry.config(fg=C_DIM)

    def _send_command(self, _event=None):
        cmd = self.cmd_entry.get().strip()
        if not cmd or cmd == self._PLACEHOLDER:
            return
        self.cmd_entry.delete(0, tk.END)
        import threading
        threading.Thread(
            target=self.app.run_custom_command,
            args=(cmd,),
            daemon=True,
        ).start()

    def _autocomplete(self, _event):
        text = self.cmd_entry.get().strip()
        if not text or text == self._PLACEHOLDER:
            return "break"
        matches = [c for c in AUTOCOMPLETE_COMMANDS if c.startswith(text)]
        if not matches:
            return "break"
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.insert(0, matches[self.autocomplete_index % len(matches)])
        self.autocomplete_index += 1
        return "break"

    # ============================================================
    # HELPERS DE WIDGETS
    # ============================================================
    def _make_flat_btn(self, parent, text, command):
        """Botao flat secundario."""
        btn = tk.Label(
            parent,
            text=text,
            bg=C_CARD,
            fg=C_TEXT,
            font=FONT_SMALL,
            padx=10,
            pady=3,
            cursor="hand2",
            relief="flat",
        )
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>",    lambda e: btn.config(bg=C_HOVER))
        btn.bind("<Leave>",    lambda e: btn.config(bg=C_CARD))
        return btn

    def _make_accent_btn(self, parent, text, command):
        """Botao de destaque (azul)."""
        btn = tk.Label(
            parent,
            text=text,
            bg=C_ACCENT,
            fg="white",
            font=FONT_SMALL,
            padx=12,
            pady=3,
            cursor="hand2",
            relief="flat",
        )
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>",    lambda e: btn.config(bg=C_ACCENT2))
        btn.bind("<Leave>",    lambda e: btn.config(bg=C_ACCENT))
        return btn