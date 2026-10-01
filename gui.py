import sys
import os
import re
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from collections import defaultdict

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from config import ACTIONS, AUTOCOMPLETE_COMMANDS, VERSION_SOFTWARE, GROUPS_FILE, DEFAULT_GROUPS, CREDITS

# ============================================================
# PALETA DE CORES
# ============================================================
C_BG      = "#15151c"
C_PANEL   = "#0e0e15"
C_SIDEBAR = "#0f0f17"
C_CARD    = "#20202c"
C_CARD2   = "#1a1a24"
C_HOVER   = "#2a2a3a"
C_BORDER  = "#2b2b3a"
C_ACCENT  = "#4a80ff"
C_ACCENT2 = "#3060cc"
C_TEXT    = "#d8d8e8"
C_DIM     = "#7676a8"
C_MUTED   = "#565680"
C_SUCCESS = "#48d890"
C_WARNING = "#f0a040"
C_DANGER  = "#e85050"
C_LOG_BG  = "#0a0a11"
C_LOG_FG  = "#38d060"

FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_H2    = ("Segoe UI", 12, "bold")
FONT_NORM  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TINY  = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 9)
FONT_GRP   = ("Segoe UI", 9, "bold")
FONT_NAV   = ("Segoe UI", 10)
FONT_ICON  = ("Segoe UI Symbol", 12)

# ============================================================
# NAVEGACAO
# Ordem e metadados das paginas da sidebar.
# icon: glyph BMP (monocromatico em Segoe UI Symbol).
# kind: "dashboard" | "actions" | "special"
# ============================================================
CATEGORY_ICONS = {
    "Otimizacao":   "⚙",   # engrenagem
    "Limpeza":      "⌧",   # delete
    "Sistema":      "☷",   # trigrama (grade)
    "Rede":         "⇅",   # setas up/down
    "Manutencao":   "⚒",   # martelo/picareta
    "Monitor":      "▤",   # quadrado com linhas
    "Privacidade":  "⚿",   # chave
    "Seguranca":    "⌨",   # (placeholder) -> ajustado abaixo
}

# ============================================================
# ORDEM DAS CATEGORIAS NA SIDEBAR (mais usadas primeiro)
# ============================================================
CATEGORY_ORDER = [
    "Otimizacao", "Limpeza", "Sistema", "Rede",
    "Manutencao", "Monitor", "Privacidade", "Seguranca",
]

# ============================================================
# EDITOR DE CODIGO - cores de sintaxe
# ============================================================
C_SYN_KW  = "#c678dd"   # palavras-chave (roxo)
C_SYN_STR = "#98c379"   # strings (verde)
C_SYN_COM = "#6b7089"   # comentarios (cinza)
C_SYN_NUM = "#d19a66"   # numeros (laranja)
C_SYN_BRK = "#56b6c2"   # () [] {} (ciano)

_KW_PY = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "self", "print", "match", "case",
}
_KW_CLIKE = {
    "auto", "bool", "break", "case", "catch", "char", "class", "const",
    "continue", "default", "delete", "do", "double", "else", "enum", "export",
    "extends", "false", "final", "finally", "float", "for", "function", "goto",
    "if", "implements", "import", "int", "interface", "let", "long", "namespace",
    "new", "null", "private", "protected", "public", "return", "short", "static",
    "struct", "switch", "this", "throw", "throws", "true", "try", "typedef",
    "typeof", "undefined", "union", "unsigned", "var", "void", "volatile",
    "while", "async", "await", "string", "number", "boolean",
}

# Extensao -> (keywords, comentario_linha, (bloco_ini, bloco_fim)|None, triple_str)
_LANG_MAP = {
    ".py":  (_KW_PY, "#", None, True),
    ".pyw": (_KW_PY, "#", None, True),
    ".c":   (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".h":   (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".cpp": (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".hpp": (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".cc":  (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".cs":  (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".java":(_KW_CLIKE, "//", ("/*", "*/"), False),
    ".js":  (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".jsx": (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".ts":  (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".tsx": (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".go":  (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".rs":  (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".php": (_KW_CLIKE, "//", ("/*", "*/"), False),
    ".json":(set(), None, None, False),
}


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# ============================================================
# SCROLLABLE FRAME
# Propaga MouseWheel de todos os filhos recursivamente
# ============================================================
class ScrollableFrame(tk.Frame):

    def __init__(self, parent, bg=C_CARD, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview,
            style="App.Vertical.TScrollbar",
        )
        self.inner = tk.Frame(self.canvas, bg=bg)

        self._win_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self._bind_scroll(self.canvas)
        self._bind_scroll(self.inner)

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._win_id, width=event.width)

    def _scroll(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_scroll(self, widget):
        widget.bind("<MouseWheel>", self._scroll, add="+")

    def bind_children_scroll(self, widget=None):
        """Propaga o bind de scroll para todos os filhos do inner frame."""
        if widget is None:
            widget = self.inner
        for child in widget.winfo_children():
            self._bind_scroll(child)
            self.bind_children_scroll(child)


# ============================================================
# GUI PRINCIPAL
# Layout estilo AIDA64:
#   HEADER
#   SIDEBAR (nav) | AREA DIREITA (barra de acao + paginas + terminal dockado)
#   STATUS BAR
# ============================================================
class GUI:

    def __init__(self, root, app):
        self.root = root
        self.app  = app

        self.autocomplete_index = 0
        self.check_vars = {}        # action_idx -> BooleanVar (global, compartilhado entre paginas)
        self.group_check_vars = {}  # action_idx -> BooleanVar (editor de grupo)

        self.pages            = {}   # nome -> Frame da pagina
        self._nav_items       = {}   # nome -> dict(widgets) do botao da sidebar
        self._current_page    = None
        self._term_expanded   = True

        self._setup_window()
        self._apply_theme()
        self._build_header()
        self._build_body()
        self._build_statusbar()

        self._show_page("Visao Geral")
        self._poll_log_queue()
        self._start_dashboard_updates()

        # Verificacao de atualizacao silenciosa (so avisa se houver nova)
        try:
            self.root.after(3000, lambda: self.app.check_updates(silent=True))
        except Exception:
            pass

    # ============================================================
    # JANELA
    # ============================================================
    def _setup_window(self):
        self.root.title(f"Sek Optimize  v{VERSION_SOFTWARE}")
        self.root.geometry("1320x760")
        self.root.minsize(1060, 640)
        self.root.configure(bg=C_BG)

        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

    # ============================================================
    # TEMA TTK
    # ============================================================
    def _apply_theme(self):
        style = ttk.Style(self.root)
        style.theme_use("default")

        style.configure("App.Vertical.TScrollbar",
            troughcolor=C_CARD, background=C_BORDER,
            borderwidth=0, arrowsize=10)

        style.configure("App.Horizontal.TProgressbar",
            troughcolor=C_CARD2, background=C_ACCENT, borderwidth=0)

        style.configure("App.TCombobox",
            fieldbackground=C_CARD, background=C_CARD2,
            foreground=C_TEXT, selectbackground=C_ACCENT,
            selectforeground="white", borderwidth=0)
        style.map("App.TCombobox",
            fieldbackground=[("readonly", C_CARD)],
            foreground=[("readonly", C_TEXT)])

        style.configure("App.Treeview",
            background=C_CARD2, fieldbackground=C_CARD2,
            foreground=C_TEXT, borderwidth=0, rowheight=22,
            font=FONT_MONO)
        style.configure("App.Treeview.Heading",
            background=C_CARD, foreground=C_ACCENT,
            font=FONT_SMALL, borderwidth=0, relief="flat")
        style.map("App.Treeview",
            background=[("selected", "#1e3050")],
            foreground=[("selected", C_TEXT)])

    # ============================================================
    # HEADER
    # ============================================================
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C_PANEL, height=50)
        hdr.pack(side=tk.TOP, fill=tk.X)
        hdr.pack_propagate(False)

        logo_wrap = tk.Frame(hdr, bg=C_PANEL)
        logo_wrap.pack(side=tk.LEFT, padx=16)

        tk.Label(logo_wrap, text="⬢", bg=C_PANEL, fg=C_ACCENT,
                 font=("Segoe UI Symbol", 16)).pack(side=tk.LEFT, pady=12)
        tk.Label(logo_wrap, text="Sek Optimize", bg=C_PANEL, fg=C_TEXT,
                 font=FONT_TITLE).pack(side=tk.LEFT, padx=(8, 0), pady=10)
        tk.Label(logo_wrap, text=f"v{VERSION_SOFTWARE}", bg=C_PANEL, fg=C_MUTED,
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=(8, 0), pady=14)

        # Busca rapida de acoes
        search_wrap = tk.Frame(hdr, bg=C_CARD, highlightthickness=1,
                               highlightbackground=C_BORDER)
        search_wrap.pack(side=tk.LEFT, padx=24, pady=10)
        tk.Label(search_wrap, text="\U0001f50d", bg=C_CARD, fg=C_MUTED,
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=(8, 2))
        self._SEARCH_PH = "Buscar acao..."
        self._search_entry = tk.Entry(
            search_wrap, bg=C_CARD, fg=C_DIM, insertbackground=C_TEXT,
            relief="flat", font=FONT_SMALL, width=30)
        self._search_entry.pack(side=tk.LEFT, padx=(0, 8), pady=4)
        self._search_entry.insert(0, self._SEARCH_PH)
        self._search_entry.bind("<FocusIn>",  self._search_focus_in)
        self._search_entry.bind("<FocusOut>", self._search_focus_out)
        self._search_entry.bind("<KeyRelease>", self._on_search)
        self._search_entry.bind("<Return>",     self._search_enter)
        self._search_entry.bind("<Escape>",     lambda e: self._hide_search_popup())
        self._search_popup = None
        self._search_results = []

        btn_about = tk.Label(
            hdr, text="Sobre o Software", bg=C_PANEL, fg=C_DIM,
            font=FONT_SMALL, padx=14, cursor="hand2",
        )
        btn_about.pack(side=tk.RIGHT, pady=12)
        btn_about.bind("<Button-1>", lambda e: self._show_credits())
        btn_about.bind("<Enter>",    lambda e: btn_about.config(fg=C_TEXT))
        btn_about.bind("<Leave>",    lambda e: btn_about.config(fg=C_DIM))

        btn_upd = tk.Label(
            hdr, text="Atualizacoes", bg=C_PANEL, fg=C_DIM,
            font=FONT_SMALL, padx=6, cursor="hand2")
        btn_upd.pack(side=tk.RIGHT, pady=12)
        btn_upd.bind("<Button-1>", lambda e: (self._show_terminal_if_hidden(),
                                              self.app.check_updates(silent=False)))
        btn_upd.bind("<Enter>",    lambda e: btn_upd.config(fg=C_TEXT))
        btn_upd.bind("<Leave>",    lambda e: btn_upd.config(fg=C_DIM))

        tk.Frame(self.root, bg=C_BORDER, height=1).pack(fill=tk.X)

    # ============================================================
    # JANELA DE CREDITOS
    # ============================================================
    def _show_credits(self):
        win = tk.Toplevel(self.root)
        win.title("Sobre")
        win.resizable(False, False)
        win.configure(bg=C_CARD)
        win.grab_set()

        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width()  // 2) - 180
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 120
        win.geometry(f"360x240+{x}+{y}")

        tk.Frame(win, bg=C_ACCENT, height=3).pack(fill=tk.X)

        body = tk.Frame(win, bg=C_CARD, padx=28, pady=20)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text="Sek Optimize", bg=C_CARD, fg=C_ACCENT,
                font=FONT_H2).pack(anchor="w")
        tk.Label(body, text=f"Versao  {VERSION_SOFTWARE}", bg=C_CARD, fg=C_DIM,
                font=FONT_SMALL).pack(anchor="w", pady=(2, 14))

        for label, value in CREDITS:
            row = tk.Frame(body, bg=C_CARD)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=f"{label}:", bg=C_CARD, fg=C_DIM,
                    font=FONT_SMALL, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, bg=C_CARD, fg=C_TEXT,
                    font=FONT_SMALL, anchor="w").pack(side=tk.LEFT)

        tk.Frame(body, bg=C_BORDER, height=1).pack(fill=tk.X, pady=(14, 10))

        tk.Label(body, text="github.com/kainandev/Sek-Optimize",
                bg=C_CARD, fg=C_DIM, font=FONT_SMALL).pack(anchor="w")

        self._make_flat_btn(body, "Fechar", win.destroy).pack(anchor="e", pady=(14, 0))

    # ============================================================
    # BUSCA RAPIDA DE ACOES
    # ============================================================
    def _search_focus_in(self, _e):
        if self._search_entry.get() == self._SEARCH_PH:
            self._search_entry.delete(0, tk.END)
            self._search_entry.config(fg=C_TEXT)

    def _search_focus_out(self, _e):
        if not self._search_entry.get():
            self._search_entry.insert(0, self._SEARCH_PH)
            self._search_entry.config(fg=C_DIM)

    def _search_matches(self, query):
        """Retorna lista de (idx, categoria, label) que casam com a busca."""
        q = query.strip().lower()
        if not q:
            return []
        out = []
        for idx, action in ACTIONS.items():
            label = action["label"]
            if q in label.lower() or q in action["tab"].lower():
                out.append((idx, action["tab"], label))
        out.sort(key=lambda t: t[2].lower())
        return out

    def _on_search(self, event=None):
        if event and event.keysym in ("Return", "Escape", "Up", "Down"):
            return
        text = self._search_entry.get()
        if text == self._SEARCH_PH:
            text = ""
        self._search_results = self._search_matches(text)[:10]
        if not self._search_results:
            self._hide_search_popup()
            return
        self._show_search_popup()

    def _show_search_popup(self):
        if self._search_popup is None:
            self._search_popup = tk.Toplevel(self.root)
            self._search_popup.overrideredirect(True)
            self._search_popup.configure(bg=C_BORDER)
            self._search_listbox = tk.Listbox(
                self._search_popup, bg=C_CARD, fg=C_TEXT,
                selectbackground=C_ACCENT, selectforeground="white",
                font=FONT_SMALL, relief="flat", borderwidth=0,
                highlightthickness=0, activestyle="none", height=10)
            self._search_listbox.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
            self._search_listbox.bind("<<ListboxSelect>>",
                                      lambda e: self._search_pick())
            self._search_listbox.bind("<Return>",
                                      lambda e: self._search_pick())

        self._search_listbox.delete(0, tk.END)
        for _idx, cat, label in self._search_results:
            self._search_listbox.insert(tk.END, f"  {cat}  ›  {label}")

        self.root.update_idletasks()
        x = self._search_entry.winfo_rootx()
        y = self._search_entry.winfo_rooty() + self._search_entry.winfo_height() + 4
        w = max(self._search_entry.winfo_width() + 40, 320)
        h = min(len(self._search_results), 10) * 20 + 4
        self._search_popup.geometry(f"{w}x{h}+{x}+{y}")
        self._search_popup.deiconify()

    def _hide_search_popup(self):
        if self._search_popup is not None:
            self._search_popup.withdraw()

    def _search_enter(self, _e=None):
        if self._search_results:
            if not self._search_listbox.curselection():
                self._search_listbox.selection_set(0)
            self._search_pick()

    def _search_pick(self):
        sel = self._search_listbox.curselection()
        if not sel or sel[0] >= len(self._search_results):
            return
        idx, cat, _label = self._search_results[sel[0]]
        self._hide_search_popup()
        self._show_page("Acoes")
        if idx in self.check_vars:
            self.check_vars[idx].set(True)
        self._search_entry.delete(0, tk.END)
        self._search_entry.insert(0, self._SEARCH_PH)
        self._search_entry.config(fg=C_DIM)
        self.root.focus_set()

    # ============================================================
    # CORPO: sidebar | area direita
    # ============================================================
    def _build_body(self):
        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True)

        self._build_sidebar(body)
        tk.Frame(body, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)
        self._build_right_area(body)

    # ============================================================
    # SIDEBAR DE NAVEGACAO
    # ============================================================
    def _build_sidebar(self, parent):
        side = tk.Frame(parent, bg=C_SIDEBAR, width=200)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)

        scroll = ScrollableFrame(side, bg=C_SIDEBAR)
        scroll.pack(fill=tk.BOTH, expand=True)
        nav = scroll.inner

        # Principal
        self._add_nav_item(nav, "Visao Geral", "◉", top=8)
        self._add_nav_item(nav, "Acoes",       "☰")

        # Ferramentas
        self._add_nav_section(nav, "FERRAMENTAS")
        self._add_nav_item(nav, "Grupos",          "❏")
        self._add_nav_item(nav, "Relatorios",      "▧")
        self._add_nav_item(nav, "E-mail",          "✉")
        self._add_nav_item(nav, "Banco de Dados",  "▤")
        self._add_nav_item(nav, "HOSTS",           "▩")
        self._add_nav_item(nav, "Inicializacao",   "⏻")
        self._add_nav_item(nav, "Programas",       "⬜")
        self._add_nav_item(nav, "Servicos",        "⚙")
        self._add_nav_item(nav, "Disco",           "◴")
        self._add_nav_item(nav, "Editor",          "✎")

        scroll.bind_children_scroll()

    def _add_nav_section(self, parent, text):
        tk.Label(parent, text=text, bg=C_SIDEBAR, fg=C_MUTED,
                 font=FONT_TINY, anchor="w", padx=16, pady=2).pack(
                     fill=tk.X, pady=(12, 2))

    def _add_nav_item(self, parent, name, icon, top=0):
        row = tk.Frame(parent, bg=C_SIDEBAR, cursor="hand2")
        row.pack(fill=tk.X, pady=(top, 0))

        strip = tk.Frame(row, bg=C_SIDEBAR, width=3)
        strip.pack(side=tk.LEFT, fill=tk.Y)

        ic = tk.Label(row, text=icon, bg=C_SIDEBAR, fg=C_DIM,
                      font=FONT_ICON, width=2)
        ic.pack(side=tk.LEFT, padx=(8, 4), pady=7)

        lbl = tk.Label(row, text=name, bg=C_SIDEBAR, fg=C_DIM,
                       font=FONT_NAV, anchor="w")
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=7)

        self._nav_items[name] = {"row": row, "strip": strip, "icon": ic, "label": lbl}

        for w in (row, ic, lbl, strip):
            w.bind("<Button-1>", lambda e, n=name: self._show_page(n))
            w.bind("<Enter>",    lambda e, n=name: self._nav_hover(n, True))
            w.bind("<Leave>",    lambda e, n=name: self._nav_hover(n, False))

    def _nav_hover(self, name, entering):
        if name == self._current_page:
            return
        it = self._nav_items[name]
        bg = C_HOVER if entering else C_SIDEBAR
        fg = C_TEXT if entering else C_DIM
        for key in ("row", "icon", "label"):
            it[key].config(bg=bg)
        it["icon"].config(fg=fg)
        it["label"].config(fg=fg)

    def _nav_set_active(self, name, active):
        it = self._nav_items[name]
        bg = C_CARD if active else C_SIDEBAR
        for key in ("row", "icon", "label"):
            it[key].config(bg=bg)
        it["strip"].config(bg=C_ACCENT if active else bg)
        it["icon"].config(fg=C_ACCENT if active else C_DIM, bg=bg)
        it["label"].config(fg=C_TEXT if active else C_DIM, bg=bg,
                           font=("Segoe UI", 10, "bold") if active else FONT_NAV)

    # ============================================================
    # AREA DIREITA: barra de acao + stack de paginas + terminal
    # ============================================================
    def _build_right_area(self, parent):
        right = tk.Frame(parent, bg=C_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Barra de acao global (so visivel em paginas de acoes)
        self._action_bar = tk.Frame(right, bg=C_CARD2, height=44)
        self._action_bar.pack_propagate(False)

        self._make_flat_btn(self._action_bar, "Selecionar tudo",
                            self._check_all_current).pack(side=tk.LEFT, padx=(10, 3), pady=8)
        self._make_flat_btn(self._action_bar, "Limpar",
                            self._uncheck_all).pack(side=tk.LEFT, padx=3, pady=8)

        self._btn_exec = self._make_accent_btn(
            self._action_bar, "Executar selecionadas", self._execute_checked)
        self._btn_exec.pack(side=tk.RIGHT, padx=10, pady=7)

        self._sel_count_lbl = tk.Label(
            self._action_bar, text="0 selecionadas", bg=C_CARD2, fg=C_DIM,
            font=FONT_SMALL)
        self._sel_count_lbl.pack(side=tk.RIGHT, padx=8)

        # Container das paginas
        self._content = tk.Frame(right, bg=C_BG)
        self._content.pack(fill=tk.BOTH, expand=True)

        # Terminal dockado
        self._build_terminal_dock(right)

        # Monta as paginas
        self._build_page_dashboard()
        self._build_page_acoes()
        self._build_page_grupos()
        self._build_page_relatorios()
        self._build_page_email()
        self._build_page_database()
        self._build_page_hosts()
        self._build_page_startup()
        self._build_page_programs()
        self._build_page_services()
        self._build_page_disk()
        self._build_page_editor()

    # ============================================================
    # ROTEAMENTO DE PAGINAS
    # ============================================================
    def _show_page(self, name):
        if name not in self.pages:
            return
        if self._current_page:
            self._nav_set_active(self._current_page, False)

        for p in self.pages.values():
            p.pack_forget()
        self.pages[name].pack(fill=tk.BOTH, expand=True)

        self._current_page = name
        self._nav_set_active(name, True)

        # Barra de acao so na pagina de Acoes
        if name == "Acoes":
            self._action_bar.pack(fill=tk.X, before=self._content)
            self._update_selection_count()
        else:
            self._action_bar.pack_forget()

    # ============================================================
    # PAGINA: VISAO GERAL (dashboard com medidores ao vivo)
    # ============================================================
    def _build_page_dashboard(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Visao Geral"] = page

        self._page_title(page, "Visao Geral",
                         "Monitoramento em tempo real e atalhos principais")

        scroll = ScrollableFrame(page, bg=C_BG)
        scroll.pack(fill=tk.BOTH, expand=True)
        inner = scroll.inner

        # --- Medidores ao vivo ---
        meters = tk.Frame(inner, bg=C_BG)
        meters.pack(fill=tk.X, padx=10, pady=(12, 4))
        for c in range(4):
            meters.columnconfigure(c, weight=1, uniform="m")

        self._dash = {}
        self._dash["cpu"]  = self._make_meter(meters, "CPU")
        self._dash["ram"]  = self._make_meter(meters, "Memoria RAM")
        self._dash["disk"] = self._make_meter(meters, "Disco C:")
        self._dash["net"]  = self._make_meter(meters, "Rede")
        for i, key in enumerate(("cpu", "ram", "disk", "net")):
            self._dash[key]["card"].grid(row=0, column=i, sticky="nsew", padx=6, pady=6)

        # --- Grafico historico (CPU / RAM) ---
        hist_card = tk.Frame(inner, bg=C_CARD, highlightthickness=1,
                             highlightbackground=C_BORDER)
        hist_card.pack(fill=tk.X, padx=16, pady=(8, 4))
        head = tk.Frame(hist_card, bg=C_CARD)
        head.pack(fill=tk.X, padx=14, pady=(10, 2))
        tk.Label(head, text="Historico (ultimos ~3 min)", bg=C_CARD, fg=C_ACCENT,
                 font=FONT_GRP).pack(side=tk.LEFT)
        tk.Label(head, text="● CPU", bg=C_CARD, fg=C_ACCENT,
                 font=FONT_TINY).pack(side=tk.RIGHT, padx=(8, 0))
        tk.Label(head, text="● RAM", bg=C_CARD, fg=C_SUCCESS,
                 font=FONT_TINY).pack(side=tk.RIGHT)
        self._hist_canvas = tk.Canvas(hist_card, height=120, bg=C_LOG_BG,
                                      highlightthickness=0)
        self._hist_canvas.pack(fill=tk.X, padx=14, pady=(2, 12))

        # --- Info do sistema ---
        info_card = tk.Frame(inner, bg=C_CARD, highlightthickness=1,
                             highlightbackground=C_BORDER)
        info_card.pack(fill=tk.X, padx=16, pady=(8, 4))
        tk.Label(info_card, text="Sistema", bg=C_CARD, fg=C_ACCENT,
                 font=FONT_GRP, anchor="w").pack(fill=tk.X, padx=14, pady=(10, 4))
        self._dash_info = tk.Label(
            info_card, text="Coletando...", bg=C_CARD, fg=C_DIM,
            font=FONT_MONO, anchor="w", justify="left")
        self._dash_info.pack(fill=tk.X, padx=14, pady=(0, 12))

        # --- Atalhos por categoria ---
        tk.Label(inner, text="Categorias", bg=C_BG, fg=C_MUTED,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X, padx=16, pady=(6, 0))
        grid = tk.Frame(inner, bg=C_BG)
        grid.pack(fill=tk.X, padx=10)
        for c in range(4):
            grid.columnconfigure(c, weight=1, uniform="d")

        counts = defaultdict(int)
        for a in ACTIONS.values():
            counts[a["tab"]] += 1

        for pos, cat in enumerate(sorted(counts.keys())):
            r, c = divmod(pos, 4)
            tile = tk.Frame(grid, bg=C_CARD, cursor="hand2",
                            highlightthickness=1, highlightbackground=C_BORDER)
            tile.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
            tk.Label(tile, text=CATEGORY_ICONS.get(cat, "▪"),
                     bg=C_CARD, fg=C_ACCENT, font=("Segoe UI Symbol", 16)).pack(
                         anchor="w", padx=12, pady=(10, 0))
            tk.Label(tile, text=cat, bg=C_CARD, fg=C_TEXT,
                     font=FONT_NORM, anchor="w").pack(fill=tk.X, padx=12)
            tk.Label(tile, text=f"{counts[cat]} acoes", bg=C_CARD, fg=C_DIM,
                     font=FONT_SMALL, anchor="w").pack(fill=tk.X, padx=12, pady=(0, 10))
            for w in (tile, *tile.winfo_children()):
                w.bind("<Button-1>", lambda e: self._show_page("Acoes"))

        scroll.bind_children_scroll()

    def _make_meter(self, parent, title):
        card = tk.Frame(parent, bg=C_CARD, highlightthickness=1,
                        highlightbackground=C_BORDER)
        tk.Label(card, text=title, bg=C_CARD, fg=C_DIM, font=FONT_SMALL,
                 anchor="w").pack(fill=tk.X, padx=12, pady=(10, 0))
        val = tk.Label(card, text="--", bg=C_CARD, fg=C_TEXT,
                       font=("Segoe UI", 17, "bold"), anchor="w")
        val.pack(fill=tk.X, padx=12)
        sub = tk.Label(card, text="", bg=C_CARD, fg=C_MUTED, font=FONT_TINY,
                       anchor="w")
        sub.pack(fill=tk.X, padx=12)
        cv = tk.Canvas(card, height=6, bg=C_CARD2, highlightthickness=0)
        cv.pack(fill=tk.X, padx=12, pady=(6, 12))
        return {"card": card, "val": val, "sub": sub, "cv": cv}

    def _set_meter(self, m, pct, value_text, sub_text=""):
        pct = max(0.0, min(100.0, pct))
        m["val"].config(text=value_text)
        m["sub"].config(text=sub_text)
        color = C_SUCCESS if pct < 60 else (C_WARNING if pct < 85 else C_DANGER)
        cv = m["cv"]
        cv.delete("bar")
        w = cv.winfo_width() or 180
        cv.create_rectangle(0, 0, int(w * pct / 100), 6,
                            fill=color, width=0, tags="bar")

    def _start_dashboard_updates(self):
        self._net_last = None
        self._hist_cpu = []
        self._hist_ram = []
        self._update_dashboard()

    def _draw_history(self):
        cv = getattr(self, "_hist_canvas", None)
        if cv is None:
            return
        cv.delete("all")
        w = cv.winfo_width() or 600
        h = cv.winfo_height() or 120
        # Linhas de grade horizontais (25/50/75%)
        for frac in (0.25, 0.5, 0.75):
            y = h * frac
            cv.create_line(0, y, w, y, fill=C_BORDER)
        for series, color in ((self._hist_cpu, C_ACCENT),
                              (self._hist_ram, C_SUCCESS)):
            n = len(series)
            if n < 2:
                continue
            step = w / (max(n, 2) - 1)
            pts = []
            for i, val in enumerate(series):
                x = i * step
                y = h - (max(0, min(100, val)) / 100.0) * h
                pts.extend((x, y))
            cv.create_line(*pts, fill=color, width=2, smooth=True)

    def _update_dashboard(self):
        if _HAS_PSUTIL and getattr(self, "_dash", None):
            try:
                cpu = psutil.cpu_percent(None)
                self._set_meter(self._dash["cpu"], cpu, f"{cpu:.0f}%",
                                f"{psutil.cpu_count(logical=True)} threads")

                vm = psutil.virtual_memory()
                self._set_meter(self._dash["ram"], vm.percent, f"{vm.percent:.0f}%",
                                f"{vm.used/(1024**3):.1f} / {vm.total/(1024**3):.1f} GB")

                sysdrive = os.environ.get("SystemDrive", "C:") + "\\"
                du = psutil.disk_usage(sysdrive)
                self._set_meter(self._dash["disk"], du.percent, f"{du.percent:.0f}%",
                                f"{du.used/(1024**3):.0f} / {du.total/(1024**3):.0f} GB")

                io = psutil.net_io_counters()
                now = time.time()
                total = io.bytes_sent + io.bytes_recv
                if self._net_last:
                    dt = now - self._net_last[1]
                    mbps = ((total - self._net_last[0]) * 8 / 1_000_000) / dt if dt > 0 else 0
                    self._set_meter(self._dash["net"], min(mbps, 100),
                                    f"{mbps:.1f} Mbps", "trafego total")
                self._net_last = (total, now)

                # Historico para o grafico (cap ~120 amostras)
                self._hist_cpu.append(cpu)
                self._hist_ram.append(vm.percent)
                if len(self._hist_cpu) > 120:
                    self._hist_cpu.pop(0)
                    self._hist_ram.pop(0)
                self._draw_history()

                self._dash_info.config(text=self._system_info_text())
            except Exception:
                pass
        self.root.after(1500, self._update_dashboard)

    def _system_info_text(self):
        try:
            import platform, socket, getpass
            boot = time.time() - psutil.boot_time()
            up = time.strftime("%Hh %Mm", time.gmtime(boot))
            return (
                f"Maquina    : {socket.gethostname()}   "
                f"Usuario : {getpass.getuser()}\n"
                f"Sistema    : {platform.system()} {platform.release()} "
                f"(build {platform.version()})\n"
                f"Processador: {platform.processor()[:60]}\n"
                f"Uptime     : {up}"
            )
        except Exception:
            return ""

    # ============================================================
    # PAGINA UNICA DE ACOES
    # Todas as acoes numa so pagina, separadas por secoes de categoria,
    # em cards de 2 colunas. A selecao e compartilhada entre as secoes,
    # permitindo marcar itens de categorias diferentes e executar juntos.
    # ============================================================
    def _build_page_acoes(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Acoes"] = page

        self._page_title(page, "Acoes",
                         f"{len(ACTIONS)} acoes em {len({a['tab'] for a in ACTIONS.values()})} categorias")

        scroll = ScrollableFrame(page, bg=C_BG)
        scroll.pack(fill=tk.BOTH, expand=True)
        inner = scroll.inner

        tabs_presentes = {a["tab"] for a in ACTIONS.values()}
        ordered = [c for c in CATEGORY_ORDER if c in tabs_presentes]
        ordered += [c for c in sorted(tabs_presentes) if c not in ordered]

        for cat in ordered:
            indices = sorted([i for i, a in ACTIONS.items() if a["tab"] == cat])

            # Cabecalho da secao
            hdr = tk.Frame(inner, bg=C_CARD2)
            hdr.pack(fill=tk.X, pady=(12, 0))
            tk.Label(hdr,
                     text=f"  {CATEGORY_ICONS.get(cat, '')}  {cat}   ({len(indices)})",
                     bg=C_CARD2, fg=C_ACCENT, font=FONT_GRP,
                     anchor="w", pady=6).pack(fill=tk.X)
            tk.Frame(inner, bg=C_BORDER, height=1).pack(fill=tk.X)

            # Grade de cards da categoria
            grid = tk.Frame(inner, bg=C_BG)
            grid.pack(fill=tk.X)
            grid.columnconfigure(0, weight=1, uniform="col")
            grid.columnconfigure(1, weight=1, uniform="col")
            for pos, idx in enumerate(indices):
                r, c = divmod(pos, 2)
                card = self._make_action_card(grid, idx)
                card.grid(row=r, column=c, sticky="nsew",
                          padx=(16 if c == 0 else 8, 16 if c == 1 else 8),
                          pady=6)

        scroll.bind_children_scroll()

    def _make_action_card(self, parent, idx):
        action = ACTIONS[idx]
        danger = action.get("danger", False)
        accent = C_WARNING if danger else C_TEXT

        var = tk.BooleanVar(value=self.check_vars[idx].get()
                            if idx in self.check_vars else False)
        self.check_vars[idx] = var
        var.trace_add("write", lambda *_: self._update_selection_count())

        card = tk.Frame(parent, bg=C_CARD, highlightthickness=1,
                        highlightbackground=C_BORDER)

        head = tk.Frame(card, bg=C_CARD)
        head.pack(fill=tk.X, padx=10, pady=(10, 2))

        chk = tk.Checkbutton(
            head, variable=var, bg=C_CARD, activebackground=C_CARD,
            fg=accent, selectcolor=C_CARD2,
            highlightthickness=0, borderwidth=0, relief="flat",
        )
        chk.pack(side=tk.LEFT)

        title = tk.Label(head, text=action["label"], bg=C_CARD, fg=accent,
                         font=("Segoe UI", 10, "bold"), anchor="w", justify="left")
        title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if danger:
            tk.Label(head, text="⚠", bg=C_CARD, fg=C_WARNING,
                     font=FONT_SMALL).pack(side=tk.RIGHT)

        desc = tk.Label(card, text=action.get("description", ""),
                        bg=C_CARD, fg=C_DIM, font=FONT_SMALL,
                        anchor="nw", justify="left", wraplength=250)
        desc.pack(fill=tk.X, padx=10, pady=(0, 10))

        def _toggle(_e=None, v=var):
            v.set(not v.get())

        def _enter(_e, c=card, parts=(card, head, title, desc)):
            for p in parts:
                p.config(bg=C_HOVER)
            chk.config(bg=C_HOVER, activebackground=C_HOVER)
            title.config(bg=C_HOVER)
            desc.config(bg=C_HOVER)
            head.config(bg=C_HOVER)
            c.config(highlightbackground=C_ACCENT)

        def _leave(_e, c=card, parts=(card, head, title, desc)):
            for p in parts:
                p.config(bg=C_CARD)
            chk.config(bg=C_CARD, activebackground=C_CARD)
            title.config(bg=C_CARD)
            desc.config(bg=C_CARD)
            head.config(bg=C_CARD)
            c.config(highlightbackground=C_BORDER)

        for w in (card, head, title, desc):
            w.bind("<Button-1>", _toggle)
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)

        return card

    def _update_selection_count(self):
        n = sum(1 for v in self.check_vars.values() if v.get())
        if hasattr(self, "_sel_count_lbl"):
            self._sel_count_lbl.config(
                text=f"{n} selecionada" + ("" if n == 1 else "s"),
                fg=C_ACCENT if n else C_DIM)

    def _check_all_current(self):
        for var in self.check_vars.values():
            var.set(True)

    def _uncheck_all(self):
        for var in self.check_vars.values():
            var.set(False)

    def _execute_checked(self):
        selected = sorted([idx for idx, var in self.check_vars.items() if var.get()])
        if not selected:
            messagebox.showinfo("Nenhuma acao",
                "Selecione ao menos uma acao antes de executar.")
            return
        threading.Thread(
            target=self.app.execute_sequence,
            args=(selected,),
            daemon=True,
        ).start()

    # ============================================================
    # TITULO PADRAO DE PAGINA
    # ============================================================
    def _page_title(self, parent, title, subtitle=""):
        head = tk.Frame(parent, bg=C_BG)
        head.pack(fill=tk.X, padx=16, pady=(14, 8))
        tk.Label(head, text=title, bg=C_BG, fg=C_TEXT,
                 font=FONT_TITLE, anchor="w").pack(anchor="w")
        if subtitle:
            tk.Label(head, text=subtitle, bg=C_BG, fg=C_MUTED,
                     font=FONT_SMALL, anchor="w").pack(anchor="w")
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X, padx=16)

    # ============================================================
    # PAGINA: GRUPOS
    # ============================================================
    def _build_page_grupos(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Grupos"] = page

        self._custom_groups = self._load_custom_groups()

        self._page_title(page, "Grupos",
                         "Conjuntos de acoes executados em sequencia")

        toolbar = tk.Frame(page, bg=C_CARD2, height=44)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        self._make_flat_btn(toolbar, "Novo Grupo",
                            self._new_group).pack(side=tk.LEFT, padx=(10, 3), pady=8)
        self._make_flat_btn(toolbar, "Excluir",
                            self._delete_group).pack(side=tk.LEFT, padx=3, pady=8)
        self._make_flat_btn(toolbar, "Exportar",
                            self._export_groups).pack(side=tk.LEFT, padx=3, pady=8)
        self._make_flat_btn(toolbar, "Importar",
                            self._import_groups).pack(side=tk.LEFT, padx=3, pady=8)
        self._make_accent_btn(toolbar, "Executar Grupo",
                              self._run_group).pack(side=tk.RIGHT, padx=10, pady=7)

        pane = tk.Frame(page, bg=C_BG)
        pane.pack(fill=tk.BOTH, expand=True)

        list_frame = tk.Frame(pane, bg=C_CARD2, width=180)
        list_frame.pack(side=tk.LEFT, fill=tk.Y)
        list_frame.pack_propagate(False)

        tk.Label(list_frame, text="Grupos", bg=C_CARD2, fg=C_DIM,
                 font=FONT_SMALL, anchor="w", padx=10, pady=6).pack(fill=tk.X)
        tk.Frame(list_frame, bg=C_BORDER, height=1).pack(fill=tk.X)

        self.groups_listbox = tk.Listbox(
            list_frame,
            bg=C_CARD2, fg=C_TEXT,
            selectbackground="#1e3050", selectforeground=C_TEXT,
            font=FONT_NORM, relief="flat", borderwidth=0,
            highlightthickness=0, activestyle="none",
        )
        self.groups_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.groups_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        tk.Frame(pane, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        edit_outer = tk.Frame(pane, bg=C_BG)
        edit_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        name_frame = tk.Frame(edit_outer, bg=C_CARD2, height=40)
        name_frame.pack(fill=tk.X)
        name_frame.pack_propagate(False)

        tk.Label(name_frame, text="Nome:", bg=C_CARD2, fg=C_DIM,
                 font=FONT_SMALL, padx=10).pack(side=tk.LEFT, pady=8)

        self.group_name_var = tk.StringVar()
        self._group_name_entry = tk.Entry(
            name_frame, textvariable=self.group_name_var,
            bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
            relief="flat", font=FONT_NORM,
        )
        self._group_name_entry.pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=6)

        self._group_type_label = tk.Label(
            name_frame, text="", bg=C_CARD2, fg=C_DIM, font=FONT_SMALL)
        self._group_type_label.pack(side=tk.LEFT, padx=4)

        self._btn_salvar = self._make_flat_btn(
            name_frame, "Salvar", self._save_group)
        self._btn_salvar.pack(side=tk.RIGHT, padx=8, pady=6)

        tk.Frame(edit_outer, bg=C_BORDER, height=1).pack(fill=tk.X)

        tk.Label(edit_outer, text="Acoes do grupo:",
                 bg=C_BG, fg=C_DIM, font=FONT_SMALL,
                 anchor="w", padx=10, pady=5).pack(fill=tk.X)

        self._scroll_grupos = ScrollableFrame(edit_outer, bg=C_CARD)
        self._scroll_grupos.pack(fill=tk.BOTH, expand=True)

        self._current_group_is_builtin = False
        self._populate_group_editor()
        self._refresh_groups_list()

    def _all_groups(self):
        merged = {}
        for name, data in DEFAULT_GROUPS.items():
            merged[name] = data
        for name, data in self._custom_groups.items():
            merged[name] = data
        return merged

    def _populate_group_editor(self, preset_indices=None, readonly=False):
        preset = set(preset_indices or [])
        inner  = self._scroll_grupos.inner
        for w in inner.winfo_children():
            w.destroy()
        self.group_check_vars.clear()

        groups = defaultdict(list)
        for idx, action in ACTIONS.items():
            groups[action["tab"]].append(idx)

        for group_name in sorted(groups.keys()):
            indices = sorted(groups[group_name])

            grp_hdr = tk.Frame(inner, bg=C_CARD2)
            grp_hdr.pack(fill=tk.X, pady=(6, 0))
            self._scroll_grupos._bind_scroll(grp_hdr)

            tk.Label(grp_hdr, text=f"  {group_name}", bg=C_CARD2,
                     fg=C_ACCENT, font=FONT_GRP,
                     anchor="w", pady=4).pack(fill=tk.X)
            self._scroll_grupos._bind_scroll(grp_hdr.winfo_children()[-1])

            tk.Frame(inner, bg=C_BORDER, height=1).pack(fill=tk.X)

            for idx in indices:
                action = ACTIONS[idx]
                var    = tk.BooleanVar(value=(idx in preset))
                self.group_check_vars[idx] = var
                color  = C_WARNING if action["danger"] else C_TEXT

                row = tk.Frame(inner, bg=C_CARD)
                row.pack(fill=tk.X)
                self._scroll_grupos._bind_scroll(row)

                state = "disabled" if readonly else "normal"

                chk = tk.Checkbutton(
                    row, variable=var,
                    bg=C_CARD, activebackground=C_HOVER,
                    fg=color, selectcolor=C_CARD2,
                    highlightthickness=0, borderwidth=0, relief="flat",
                    state=state,
                )
                chk.pack(side=tk.LEFT, padx=(8, 2), pady=3)
                self._scroll_grupos._bind_scroll(chk)

                lbl = tk.Label(row, text=action["label"], bg=C_CARD,
                               fg=color if not readonly else C_DIM,
                               font=FONT_NORM, anchor="w")
                lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=3)
                self._scroll_grupos._bind_scroll(lbl)

                if not readonly:
                    lbl.bind("<Button-1>", lambda e, v=var: v.set(not v.get()))
                    for w in (row, lbl, chk):
                        w.bind("<Enter>", lambda e, r=row, c=chk: (
                            r.config(bg=C_HOVER), c.config(bg=C_HOVER)))
                        w.bind("<Leave>", lambda e, r=row, c=chk: (
                            r.config(bg=C_CARD), c.config(bg=C_CARD)))

    def _on_group_select(self, _event):
        sel = self.groups_listbox.curselection()
        if not sel:
            return
        name  = self.groups_listbox.get(sel[0])
        all_g = self._all_groups()
        group = all_g.get(name, {})
        is_builtin = group.get("builtin", False)

        self._current_group_is_builtin = is_builtin
        self.group_name_var.set(name)
        self._group_name_entry.config(state="disabled" if is_builtin else "normal")
        self._btn_salvar.config(fg=C_DIM if is_builtin else C_TEXT,
                                cursor="arrow" if is_builtin else "hand2")
        self._group_type_label.config(
            text="(padrao)" if is_builtin else "(customizado)", fg=C_DIM)

        self._populate_group_editor(
            preset_indices=group.get("actions", []),
            readonly=is_builtin,
        )

    def _new_group(self):
        self.groups_listbox.selection_clear(0, tk.END)
        self.group_name_var.set("")
        self._group_name_entry.config(state="normal")
        self._btn_salvar.config(fg=C_TEXT, cursor="hand2")
        self._group_type_label.config(text="")
        self._current_group_is_builtin = False
        self._populate_group_editor()

    def _save_group(self):
        if self._current_group_is_builtin:
            messagebox.showinfo("Grupo padrao",
                "Grupos padrao nao podem ser editados.\n"
                "Crie um novo grupo para personalizacoes.")
            return
        name = self.group_name_var.get().strip()
        if not name:
            messagebox.showwarning("Nome vazio", "Informe um nome para o grupo.")
            return
        if name in DEFAULT_GROUPS:
            messagebox.showwarning("Nome reservado",
                f"'{name}' e o nome de um grupo padrao. Use outro nome.")
            return
        selected = sorted([i for i, v in self.group_check_vars.items() if v.get()])
        if not selected:
            messagebox.showwarning("Grupo vazio", "Selecione ao menos uma acao.")
            return
        self._custom_groups[name] = {"actions": selected}
        self._save_custom_groups()
        self._refresh_groups_list()
        messagebox.showinfo("Salvo",
            f"Grupo '{name}' salvo com {len(selected)} acao(oes).")

    def _delete_group(self):
        sel = self.groups_listbox.curselection()
        if not sel:
            messagebox.showinfo("Nenhum grupo", "Selecione um grupo para excluir.")
            return
        name = self.groups_listbox.get(sel[0])
        if name in DEFAULT_GROUPS:
            messagebox.showinfo("Grupo padrao", "Grupos padrao nao podem ser excluidos.")
            return
        if messagebox.askyesno("Excluir grupo", f"Excluir o grupo '{name}'?"):
            self._custom_groups.pop(name, None)
            self._save_custom_groups()
            self._refresh_groups_list()
            self._new_group()

    def _run_group(self):
        sel = self.groups_listbox.curselection()
        if not sel:
            messagebox.showinfo("Nenhum grupo", "Selecione um grupo para executar.")
            return
        name    = self.groups_listbox.get(sel[0])
        all_g   = self._all_groups()
        indices = all_g.get(name, {}).get("actions", [])
        if not indices:
            messagebox.showinfo("Grupo vazio", "Este grupo nao possui acoes.")
            return
        threading.Thread(
            target=self.app.execute_sequence,
            args=(indices,),
            daemon=True,
        ).start()

    def _refresh_groups_list(self):
        self.groups_listbox.delete(0, tk.END)
        for name in DEFAULT_GROUPS:
            self.groups_listbox.insert(tk.END, name)
        for name in sorted(self._custom_groups.keys()):
            self.groups_listbox.insert(tk.END, name)

    # ============================================================
    # EXPORT / IMPORT DE GRUPOS CUSTOMIZADOS
    # ============================================================
    def _export_groups(self):
        if not self._custom_groups:
            messagebox.showinfo("Exportar", "Nenhum grupo customizado para exportar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="Exportar grupos",
            initialfile="sek_grupos.json",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._custom_groups, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Exportado",
                f"{len(self._custom_groups)} grupo(s) exportado(s) para:\n{path}")
        except Exception as e:
            messagebox.showerror("Erro ao exportar", str(e))

    def _import_groups(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")],
            title="Importar grupos",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                imported = json.load(f)
            if not isinstance(imported, dict):
                raise ValueError("Formato invalido.")
            valid = {
                k: v for k, v in imported.items()
                if isinstance(v, dict) and isinstance(v.get("actions"), list)
            }
            if not valid:
                raise ValueError("Nenhum grupo valido encontrado no arquivo.")
            conflitos = [k for k in valid if k in self._custom_groups]
            if conflitos and not messagebox.askyesno(
                "Conflito",
                f"Os grupos a seguir ja existem e serao sobrescritos:\n"
                f"{', '.join(conflitos)}\n\nContinuar?"
            ):
                return
            self._custom_groups.update(valid)
            self._save_custom_groups()
            self._refresh_groups_list()
            messagebox.showinfo("Importado", f"{len(valid)} grupo(s) importado(s).")
        except Exception as e:
            messagebox.showerror("Erro ao importar", str(e))

    def _load_custom_groups(self):
        if os.path.exists(GROUPS_FILE):
            try:
                with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_custom_groups(self):
        try:
            with open(GROUPS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._custom_groups, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============================================================
    # PAGINA: RELATORIOS
    # ============================================================
    def _build_page_relatorios(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Relatorios"] = page

        self._page_title(page, "Relatorios",
                         "Exportar, enviar e converter relatorios do sistema")

        scroll    = ScrollableFrame(page, bg=C_BG)
        scroll.pack(fill=tk.BOTH, expand=True)
        container = scroll.inner

        # SECAO 1: Exportar para Arquivo
        self._report_section(container, "Exportar para Arquivo")
        sec1_body = tk.Frame(container, bg=C_BG)
        sec1_body.pack(fill=tk.X, padx=16, pady=10)

        tk.Label(sec1_body, text="Formato:", bg=C_BG, fg=C_DIM,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X)

        self._report_fmt = tk.StringVar(value="json")
        radio_row = tk.Frame(sec1_body, bg=C_BG)
        radio_row.pack(fill=tk.X, pady=(3, 10))
        for fmt_opt in ("json", "csv", "html"):
            tk.Radiobutton(
                radio_row, text=fmt_opt.upper(),
                variable=self._report_fmt, value=fmt_opt,
                bg=C_BG, fg=C_TEXT, selectcolor=C_CARD2,
                activebackground=C_BG, activeforeground=C_TEXT,
                highlightthickness=0, font=FONT_SMALL,
            ).pack(side=tk.LEFT, padx=(0, 14))

        tk.Label(sec1_body, text="Destino:", bg=C_BG, fg=C_DIM,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X)

        self._report_path_var = tk.StringVar()
        path_row = tk.Frame(sec1_body, bg=C_BG)
        path_row.pack(fill=tk.X, pady=(3, 10))
        tk.Entry(path_row, textvariable=self._report_path_var,
                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", font=FONT_MONO).pack(
                     side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self._make_flat_btn(path_row, "Buscar",
                            self._browse_report_path).pack(side=tk.LEFT, padx=(4, 0))

        export_row = tk.Frame(sec1_body, bg=C_BG)
        export_row.pack(fill=tk.X)
        self._btn_export = tk.Label(
            export_row, text="Exportar", bg=C_CARD2, fg=C_DIM,
            font=FONT_SMALL, padx=14, pady=4, cursor="arrow", relief="flat")
        self._btn_export.pack(side=tk.RIGHT)
        self._btn_export.bind("<Button-1>", lambda e: self._do_export())

        # SECAO 2: Enviar para API
        self._report_section(container, "Enviar para API")
        sec2_body = tk.Frame(container, bg=C_BG)
        sec2_body.pack(fill=tk.X, padx=16, pady=10)

        tk.Label(sec2_body, text="Metodo HTTP:", bg=C_BG, fg=C_DIM,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X)
        self._api_method_var = tk.StringVar(value="POST")
        ttk.Combobox(sec2_body, textvariable=self._api_method_var,
                     values=["POST", "PUT", "PATCH"], state="readonly",
                     style="App.TCombobox", font=FONT_SMALL, width=10).pack(
                         anchor="w", pady=(3, 10))

        tk.Label(sec2_body, text="URL:", bg=C_BG, fg=C_DIM,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X)
        self._api_url_var = tk.StringVar()
        tk.Entry(sec2_body, textvariable=self._api_url_var,
                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", font=FONT_MONO).pack(fill=tk.X, pady=(3, 10), ipady=4)

        tk.Label(sec2_body, text="Chave de Acesso:", bg=C_BG, fg=C_DIM,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X)
        self._api_key_var = tk.StringVar()
        tk.Entry(sec2_body, textvariable=self._api_key_var,
                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", font=FONT_MONO, show="*").pack(
                     fill=tk.X, pady=(3, 10), ipady=4)

        send_row = tk.Frame(sec2_body, bg=C_BG)
        send_row.pack(fill=tk.X)
        self._btn_send = tk.Label(
            send_row, text="Enviar", bg=C_CARD2, fg=C_DIM,
            font=FONT_SMALL, padx=14, pady=4, cursor="arrow", relief="flat")
        self._btn_send.pack(side=tk.RIGHT)
        self._btn_send.bind("<Button-1>", lambda e: self._do_send_api())

        # SECAO 3: Converter JSON para HTML
        self._report_section(container, "Converter JSON para HTML")
        sec3_body = tk.Frame(container, bg=C_BG)
        sec3_body.pack(fill=tk.X, padx=16, pady=10)

        tk.Label(sec3_body, text="Origem:", bg=C_BG, fg=C_DIM,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X)
        self._convert_mode = tk.StringVar(value="file")
        convert_radio_row = tk.Frame(sec3_body, bg=C_BG)
        convert_radio_row.pack(fill=tk.X, pady=(3, 10))
        tk.Radiobutton(convert_radio_row, text="Arquivo JSON",
            variable=self._convert_mode, value="file",
            bg=C_BG, fg=C_TEXT, selectcolor=C_CARD2,
            activebackground=C_BG, activeforeground=C_TEXT,
            highlightthickness=0, font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 14))
        tk.Radiobutton(convert_radio_row, text="Pasta (varios JSONs)",
            variable=self._convert_mode, value="folder",
            bg=C_BG, fg=C_TEXT, selectcolor=C_CARD2,
            activebackground=C_BG, activeforeground=C_TEXT,
            highlightthickness=0, font=FONT_SMALL).pack(side=tk.LEFT)

        tk.Label(sec3_body, text="Caminho:", bg=C_BG, fg=C_DIM,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X)
        self._convert_path_var = tk.StringVar()
        convert_path_row = tk.Frame(sec3_body, bg=C_BG)
        convert_path_row.pack(fill=tk.X, pady=(3, 4))
        tk.Entry(convert_path_row, textvariable=self._convert_path_var,
                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", font=FONT_MONO).pack(
                     side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self._make_flat_btn(convert_path_row, "Buscar",
                            self._browse_convert_path).pack(side=tk.LEFT, padx=(4, 0))

        tk.Label(sec3_body,
                 text="Pasta gera um unico HTML consolidado, com cada maquina e "
                      "suas secoes na barra lateral.",
                 bg=C_BG, fg=C_DIM, font=FONT_SMALL,
                 anchor="w", justify="left", wraplength=420).pack(
                     fill=tk.X, pady=(0, 8))

        convert_row = tk.Frame(sec3_body, bg=C_BG)
        convert_row.pack(fill=tk.X)
        self._btn_convert = tk.Label(
            convert_row, text="Converter", bg=C_CARD2, fg=C_DIM,
            font=FONT_SMALL, padx=14, pady=4, cursor="arrow", relief="flat")
        self._btn_convert.pack(side=tk.RIGHT)
        self._btn_convert.bind("<Button-1>", lambda e: self._do_convert())

        self._report_path_var.trace("w",  self._update_export_btn)
        self._api_url_var.trace("w",      self._update_send_btn)
        self._api_key_var.trace("w",      self._update_send_btn)
        self._convert_path_var.trace("w", self._update_convert_btn)

        scroll.bind_children_scroll()

    def _report_section(self, parent, title):
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X, pady=(10, 0))
        hdr = tk.Frame(parent, bg=C_CARD2)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=f"  {title}", bg=C_CARD2, fg=C_ACCENT,
                 font=FONT_GRP, anchor="w", pady=8).pack(fill=tk.X)
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)

    # ============================================================
    # CALLBACKS DA PAGINA RELATORIOS
    # ============================================================
    def _browse_report_path(self):
        fmt     = self._report_fmt.get()
        ext_map = {"json": ".json", "csv": ".csv", "html": ".html"}
        ext     = ext_map.get(fmt, ".json")
        path    = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(fmt.upper(), f"*{ext}"), ("Todos", "*.*")],
            title="Salvar relatorio",
            initialfile=f"relatorio_sek{ext}",
        )
        if path:
            self._report_path_var.set(path)

    def _set_btn_active(self, btn):
        btn.config(bg=C_ACCENT, fg="white", cursor="hand2")
        btn.bind("<Enter>", lambda e: btn.config(bg=C_ACCENT2))
        btn.bind("<Leave>", lambda e: btn.config(bg=C_ACCENT))

    def _set_btn_inactive(self, btn):
        btn.config(bg=C_CARD2, fg=C_DIM, cursor="arrow")
        btn.bind("<Enter>", lambda e: None)
        btn.bind("<Leave>", lambda e: None)

    def _update_export_btn(self, *_):
        if self._report_path_var.get().strip():
            self._set_btn_active(self._btn_export)
        else:
            self._set_btn_inactive(self._btn_export)

    def _update_send_btn(self, *_):
        url_ok = bool(self._api_url_var.get().strip())
        key_ok = bool(self._api_key_var.get().strip())
        if url_ok and key_ok:
            self._set_btn_active(self._btn_send)
        else:
            self._set_btn_inactive(self._btn_send)

    def _do_export(self):
        path = self._report_path_var.get().strip()
        fmt  = self._report_fmt.get()
        if not path:
            return
        self.app.export_report(fmt, path)

    def _do_send_api(self):
        url = self._api_url_var.get().strip()
        key = self._api_key_var.get().strip()
        if not url or not key:
            return
        method = self._api_method_var.get()
        self.app.send_report_api(url, key, method)

    def _browse_convert_path(self):
        if self._convert_mode.get() == "folder":
            path = filedialog.askdirectory(
                title="Selecione a pasta com os arquivos JSON")
        else:
            path = filedialog.askopenfilename(
                title="Selecione o JSON", filetypes=[("JSON", "*.json")])
        if path:
            self._convert_path_var.set(path)

    def _update_convert_btn(self, *_):
        if self._convert_path_var.get().strip():
            self._set_btn_active(self._btn_convert)
        else:
            self._set_btn_inactive(self._btn_convert)

    def _do_convert(self):
        path = self._convert_path_var.get().strip()
        if not path:
            return
        is_folder = self._convert_mode.get() == "folder"
        self.app.convert_json_to_html(path, is_folder)

    # ============================================================
    # PAGINA: E-MAIL (conversao PST/OST/MBOX)
    # ============================================================
    def _build_page_email(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["E-mail"] = page

        self._page_title(page, "E-mail",
                         "Converter caixas de correio entre formatos")

        scroll = ScrollableFrame(page, bg=C_BG)
        scroll.pack(fill=tk.BOTH, expand=True)
        body = scroll.inner

        # Explicacao
        note = tk.Frame(body, bg=C_CARD2)
        note.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(
            note,
            text=("Leitura de PST/OST e feita direto do arquivo, sem precisar do "
                  "Outlook.\nComo o Thunderbird importa MBOX nativamente, use MBOX "
                  "para levar e-mails ao Thunderbird.\nGravar em PST requer o "
                  "Microsoft Outlook instalado (melhor esforco)."),
            bg=C_CARD2, fg=C_DIM, font=FONT_SMALL,
            anchor="w", justify="left", padx=12, pady=10).pack(fill=tk.X)

        form = tk.Frame(body, bg=C_BG)
        form.pack(fill=tk.X, padx=16, pady=10)

        # Origem
        tk.Label(form, text="Arquivo de origem (.pst / .ost / .mbox):",
                 bg=C_BG, fg=C_DIM, font=FONT_SMALL, anchor="w").pack(fill=tk.X)
        self._email_src_var = tk.StringVar()
        src_row = tk.Frame(form, bg=C_BG)
        src_row.pack(fill=tk.X, pady=(3, 10))
        tk.Entry(src_row, textvariable=self._email_src_var,
                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", font=FONT_MONO).pack(
                     side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self._make_flat_btn(src_row, "Buscar",
                            self._browse_email_src).pack(side=tk.LEFT, padx=(4, 0))

        # Formato de destino
        tk.Label(form, text="Converter para:", bg=C_BG, fg=C_DIM,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X)
        self._email_dst_fmt = tk.StringVar(value="mbox")
        fmt_row = tk.Frame(form, bg=C_BG)
        fmt_row.pack(fill=tk.X, pady=(3, 10))
        for val, txt in (("mbox", "MBOX (Thunderbird)"),
                         ("eml",  "EML (pasta)"),
                         ("pst",  "PST (requer Outlook)")):
            tk.Radiobutton(
                fmt_row, text=txt, variable=self._email_dst_fmt, value=val,
                bg=C_BG, fg=C_TEXT, selectcolor=C_CARD2,
                activebackground=C_BG, activeforeground=C_TEXT,
                highlightthickness=0, font=FONT_SMALL,
                command=self._email_dst_hint).pack(side=tk.LEFT, padx=(0, 14))

        # Destino
        tk.Label(form, text="Destino:", bg=C_BG, fg=C_DIM,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X)
        self._email_dst_var = tk.StringVar()
        dst_row = tk.Frame(form, bg=C_BG)
        dst_row.pack(fill=tk.X, pady=(3, 4))
        tk.Entry(dst_row, textvariable=self._email_dst_var,
                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", font=FONT_MONO).pack(
                     side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self._make_flat_btn(dst_row, "Buscar",
                            self._browse_email_dst).pack(side=tk.LEFT, padx=(4, 0))

        self._email_hint = tk.Label(
            form, text="", bg=C_BG, fg=C_MUTED, font=FONT_TINY, anchor="w")
        self._email_hint.pack(fill=tk.X, pady=(0, 8))

        conv_row = tk.Frame(form, bg=C_BG)
        conv_row.pack(fill=tk.X)
        self._btn_email = tk.Label(
            conv_row, text="Converter", bg=C_CARD2, fg=C_DIM,
            font=FONT_SMALL, padx=14, pady=4, cursor="arrow", relief="flat")
        self._btn_email.pack(side=tk.RIGHT)
        self._btn_email.bind("<Button-1>", lambda e: self._do_email_convert())

        self._email_src_var.trace("w", self._update_email_btn)
        self._email_dst_var.trace("w", self._update_email_btn)
        self._email_dst_hint()

        scroll.bind_children_scroll()

    def _email_dst_hint(self):
        fmt = self._email_dst_fmt.get()
        hints = {
            "mbox": "Gera um unico arquivo .mbox (importavel pelo Thunderbird).",
            "eml":  "Gera uma pasta com um arquivo .eml por mensagem.",
            "pst":  "Gera um .pst via Outlook (assunto/remetente/corpo/anexos).",
        }
        self._email_hint.config(text=hints.get(fmt, ""))

    def _browse_email_src(self):
        path = filedialog.askopenfilename(
            title="Selecione o arquivo de e-mail",
            filetypes=[("E-mail", "*.pst *.ost *.mbox *.mbx"),
                       ("Todos", "*.*")])
        if path:
            self._email_src_var.set(path)

    def _browse_email_dst(self):
        fmt = self._email_dst_fmt.get()
        if fmt == "eml":
            path = filedialog.askdirectory(title="Pasta de destino para os .eml")
        elif fmt == "pst":
            path = filedialog.asksaveasfilename(
                title="Salvar PST", defaultextension=".pst",
                filetypes=[("PST", "*.pst")], initialfile="convertido.pst")
        else:
            path = filedialog.asksaveasfilename(
                title="Salvar MBOX", defaultextension=".mbox",
                filetypes=[("MBOX", "*.mbox"), ("Todos", "*.*")],
                initialfile="convertido.mbox")
        if path:
            self._email_dst_var.set(path)

    def _update_email_btn(self, *_):
        if self._email_src_var.get().strip() and self._email_dst_var.get().strip():
            self._set_btn_active(self._btn_email)
        else:
            self._set_btn_inactive(self._btn_email)

    def _do_email_convert(self):
        src = self._email_src_var.get().strip()
        dst = self._email_dst_var.get().strip()
        if not src or not dst:
            return
        fmt = self._email_dst_fmt.get()
        self._show_terminal_if_hidden()
        self.app.email_convert(src, fmt, dst)

    # ============================================================
    # PAGINA: BANCO DE DADOS (SQLite)
    # ============================================================
    def _build_page_database(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Banco de Dados"] = page

        self._page_title(page, "Banco de Dados",
                         "Abrir um arquivo SQLite e executar comandos SQL")

        # Barra de abertura
        openbar = tk.Frame(page, bg=C_CARD2, height=44)
        openbar.pack(fill=tk.X)
        openbar.pack_propagate(False)

        self._db_path_var = tk.StringVar()
        tk.Entry(openbar, textvariable=self._db_path_var,
                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", font=FONT_MONO).pack(
                     side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 4), pady=8, ipady=3)
        self._make_flat_btn(openbar, "Buscar",
                            self._browse_db).pack(side=tk.LEFT, pady=8)
        self._make_accent_btn(openbar, "Abrir",
                              self._open_db).pack(side=tk.LEFT, padx=(4, 10), pady=7)

        pane = tk.Frame(page, bg=C_BG)
        pane.pack(fill=tk.BOTH, expand=True)

        # Lista de tabelas
        left = tk.Frame(pane, bg=C_CARD2, width=190)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        tk.Label(left, text="Tabelas", bg=C_CARD2, fg=C_DIM,
                 font=FONT_SMALL, anchor="w", padx=10, pady=6).pack(fill=tk.X)
        tk.Frame(left, bg=C_BORDER, height=1).pack(fill=tk.X)
        self._db_tables = tk.Listbox(
            left, bg=C_CARD2, fg=C_TEXT,
            selectbackground="#1e3050", selectforeground=C_TEXT,
            font=FONT_NORM, relief="flat", borderwidth=0,
            highlightthickness=0, activestyle="none")
        self._db_tables.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._db_tables.bind("<<ListboxSelect>>", self._on_db_table_select)

        tk.Frame(pane, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        right = tk.Frame(pane, bg=C_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Editor SQL
        tk.Label(right, text="SQL:", bg=C_BG, fg=C_DIM, font=FONT_SMALL,
                 anchor="w", padx=8, pady=4).pack(fill=tk.X)
        self._db_sql = tk.Text(
            right, height=4, bg=C_LOG_BG, fg=C_TEXT, insertbackground=C_TEXT,
            relief="flat", font=FONT_MONO, wrap="word",
            highlightthickness=1, highlightbackground=C_BORDER)
        self._db_sql.pack(fill=tk.X, padx=8)

        runbar = tk.Frame(right, bg=C_BG)
        runbar.pack(fill=tk.X, padx=8, pady=6)
        self._db_status = tk.Label(runbar, text="Nenhum banco aberto.",
                                   bg=C_BG, fg=C_MUTED, font=FONT_SMALL, anchor="w")
        self._db_status.pack(side=tk.LEFT)
        self._make_accent_btn(runbar, "Executar SQL",
                              self._run_db_query).pack(side=tk.RIGHT)
        self._make_flat_btn(runbar, "Exportar XLSX",
                            lambda: self._export_db("xlsx")).pack(side=tk.RIGHT, padx=4)
        self._make_flat_btn(runbar, "Exportar CSV",
                            lambda: self._export_db("csv")).pack(side=tk.RIGHT, padx=4)
        self._db_last = ([], [])

        # Grade de resultados
        grid_wrap = tk.Frame(right, bg=C_BG)
        grid_wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        yscroll = ttk.Scrollbar(grid_wrap, orient="vertical",
                                style="App.Vertical.TScrollbar")
        xscroll = ttk.Scrollbar(grid_wrap, orient="horizontal")
        self._db_tree = ttk.Treeview(
            grid_wrap, style="App.Treeview", show="headings",
            yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.config(command=self._db_tree.yview)
        xscroll.config(command=self._db_tree.xview)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self._db_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _browse_db(self):
        path = filedialog.askopenfilename(
            title="Selecione o banco SQLite",
            filetypes=[("SQLite", "*.db *.sqlite *.sqlite3 *.db3"),
                       ("Todos", "*.*")])
        if path:
            self._db_path_var.set(path)

    def _open_db(self):
        path = self._db_path_var.get().strip()
        if not path:
            return
        ok, msg = self.app.db_connect(path)
        self._db_status.config(text=msg, fg=C_SUCCESS if ok else C_DANGER)
        self._db_tables.delete(0, tk.END)
        if ok:
            for t in self.app.db_tables():
                n = self.app.db_row_count(t)
                self._db_tables.insert(tk.END, f"{t}  ({n})")

    def _on_db_table_select(self, _event):
        sel = self._db_tables.curselection()
        if not sel or not self.app.db_is_open():
            return
        raw = self._db_tables.get(sel[0])
        table = raw.rsplit("  (", 1)[0]
        safe = '"' + table.replace('"', '""') + '"'
        self._db_sql.delete("1.0", tk.END)
        self._db_sql.insert("1.0", f"SELECT * FROM {safe} LIMIT 200;")
        self._run_db_query()

    def _run_db_query(self):
        if not self.app.db_is_open():
            self._db_status.config(text="Abra um banco primeiro.", fg=C_WARNING)
            return
        sql = self._db_sql.get("1.0", tk.END).strip()
        res = self.app.db_query(sql)
        if not res.get("ok"):
            self._db_status.config(text=res.get("error", "Erro."), fg=C_DANGER)
            return
        self._db_status.config(text=res.get("info", ""), fg=C_SUCCESS)
        cols = res.get("columns", [])
        rows = res.get("rows", [])
        self._db_last = (cols, rows)
        self._fill_db_tree(cols, rows)

    def _export_db(self, fmt):
        cols, rows = self._db_last
        if not cols:
            self._db_status.config(text="Execute um SELECT antes de exportar.",
                                   fg=C_WARNING)
            return
        ext = ".csv" if fmt == "csv" else ".xlsx"
        path = filedialog.asksaveasfilename(
            title="Exportar resultado", defaultextension=ext,
            filetypes=[(fmt.upper(), f"*{ext}")],
            initialfile=f"consulta_sek{ext}")
        if not path:
            return
        ok, msg = self.app.db_export(cols, rows, path, fmt)
        self._db_status.config(text=msg, fg=C_SUCCESS if ok else C_DANGER)

    def _fill_db_tree(self, columns, rows):
        tree = self._db_tree
        tree.delete(*tree.get_children())
        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=140, minwidth=60, anchor="w", stretch=False)
        for row in rows:
            values = ["" if v is None else str(v) for v in row]
            tree.insert("", tk.END, values=values)

    def _show_terminal_if_hidden(self):
        if not self._term_expanded:
            self._toggle_terminal()

    # ============================================================
    # PAGINA: EDITOR DO ARQUIVO HOSTS
    # ============================================================
    def _build_page_hosts(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["HOSTS"] = page

        self._page_title(page, "Arquivo HOSTS",
                         "Editar o hosts do Windows e bloquear dominios")

        # Barra de bloqueio rapido
        block_bar = tk.Frame(page, bg=C_CARD2, height=44)
        block_bar.pack(fill=tk.X)
        block_bar.pack_propagate(False)
        tk.Label(block_bar, text="Bloquear dominio:", bg=C_CARD2, fg=C_DIM,
                 font=FONT_SMALL, padx=10).pack(side=tk.LEFT, pady=8)
        self._hosts_block_var = tk.StringVar()
        tk.Entry(block_bar, textvariable=self._hosts_block_var,
                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", font=FONT_MONO, width=30).pack(
                     side=tk.LEFT, pady=8, ipady=3)
        self._make_flat_btn(block_bar, "Bloquear",
                            self._hosts_do_block).pack(side=tk.LEFT, padx=6, pady=8)
        self._make_flat_btn(block_bar, "Recarregar",
                            self._hosts_reload).pack(side=tk.RIGHT, padx=4, pady=8)
        self._make_accent_btn(block_bar, "Salvar",
                              self._hosts_save).pack(side=tk.RIGHT, padx=(4, 10), pady=7)

        self._hosts_status = tk.Label(page, text="", bg=C_BG, fg=C_MUTED,
                                      font=FONT_SMALL, anchor="w", padx=10, pady=3)
        self._hosts_status.pack(fill=tk.X)

        self._hosts_text = tk.Text(
            page, bg=C_LOG_BG, fg=C_TEXT, insertbackground=C_TEXT,
            relief="flat", font=FONT_MONO, wrap="none",
            highlightthickness=0, borderwidth=0)
        self._hosts_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._hosts_reload()

    def _hosts_reload(self):
        ok, content = self.app.hosts_read()
        self._hosts_text.delete("1.0", tk.END)
        if ok:
            self._hosts_text.insert("1.0", content)
            self._hosts_status.config(text="Carregado.", fg=C_SUCCESS)
        else:
            self._hosts_status.config(text=content, fg=C_DANGER)

    def _hosts_save(self):
        content = self._hosts_text.get("1.0", "end-1c")
        ok, msg = self.app.hosts_save(content)
        self._hosts_status.config(text=msg, fg=C_SUCCESS if ok else C_DANGER)

    def _hosts_do_block(self):
        domain = self._hosts_block_var.get().strip()
        if not domain:
            return
        ok, msg = self.app.hosts_block(domain)
        self._hosts_status.config(text=msg, fg=C_SUCCESS if ok else C_DANGER)
        if ok:
            self._hosts_block_var.set("")
            self._hosts_reload()

    # ============================================================
    # HELPER: tabela (Treeview) com scrollbars
    # ============================================================
    def _make_table(self, parent, columns, widths):
        wrap = tk.Frame(parent, bg=C_BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        ysb = ttk.Scrollbar(wrap, orient="vertical",
                            style="App.Vertical.TScrollbar")
        xsb = ttk.Scrollbar(wrap, orient="horizontal")
        tree = ttk.Treeview(wrap, style="App.Treeview", show="headings",
                            columns=columns,
                            yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        ysb.config(command=tree.yview)
        xsb.config(command=tree.xview)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)
        xsb.pack(side=tk.BOTTOM, fill=tk.X)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for col, w in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, minwidth=50, anchor="w", stretch=True)
        return tree

    # ============================================================
    # PAGINA: INICIALIZACAO
    # ============================================================
    def _build_page_startup(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Inicializacao"] = page
        self._page_title(page, "Inicializacao",
                         "Programas que iniciam com o Windows")

        bar = tk.Frame(page, bg=C_CARD2, height=44)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        self._make_flat_btn(bar, "Recarregar",
                            self._startup_reload).pack(side=tk.LEFT, padx=(10, 3), pady=8)
        self._make_accent_btn(bar, "Habilitar",
                              lambda: self._startup_toggle(True)).pack(side=tk.LEFT, padx=3, pady=7)
        self._make_flat_btn(bar, "Desabilitar",
                            lambda: self._startup_toggle(False)).pack(side=tk.LEFT, padx=3, pady=8)
        self._startup_status = tk.Label(bar, text="", bg=C_CARD2, fg=C_MUTED,
                                        font=FONT_SMALL)
        self._startup_status.pack(side=tk.RIGHT, padx=10)

        self._startup_tree = self._make_table(
            page, ("Nome", "Local", "Estado", "Comando"),
            (200, 110, 90, 400))
        self._startup_map = {}

    def _startup_reload(self):
        items = self.app.startup_list()
        tree = self._startup_tree
        tree.delete(*tree.get_children())
        self._startup_map.clear()
        for it in items:
            estado = "Ativo" if it["enabled"] else "Desativado"
            iid = tree.insert("", tk.END, values=(
                it["name"], it["location"], estado, it["command"]))
            self._startup_map[iid] = it
        self._startup_status.config(text=f"{len(items)} entradas", fg=C_DIM)

    def _startup_toggle(self, enable):
        sel = self._startup_tree.selection()
        if not sel:
            self._startup_status.config(text="Selecione uma entrada.", fg=C_WARNING)
            return
        done = 0
        for iid in sel:
            it = self._startup_map.get(iid)
            if it:
                ok, _msg = self.app.startup_set_enabled(it, enable)
                done += 1 if ok else 0
        self._startup_reload()
        self._startup_status.config(
            text=f"{done} entrada(s) atualizada(s).", fg=C_SUCCESS)

    # ============================================================
    # PAGINA: PROGRAMAS (desinstalador)
    # ============================================================
    def _build_page_programs(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Programas"] = page
        self._page_title(page, "Programas",
                         "Programas instalados e desinstalacao")

        bar = tk.Frame(page, bg=C_CARD2, height=44)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        self._make_flat_btn(bar, "Recarregar",
                            self._programs_reload).pack(side=tk.LEFT, padx=(10, 3), pady=8)
        self._make_accent_btn(bar, "Desinstalar",
                              self._programs_uninstall).pack(side=tk.LEFT, padx=3, pady=7)
        self._programs_status = tk.Label(bar, text="", bg=C_CARD2, fg=C_MUTED,
                                         font=FONT_SMALL)
        self._programs_status.pack(side=tk.RIGHT, padx=10)

        self._programs_tree = self._make_table(
            page, ("Nome", "Versao", "Publicador"),
            (330, 120, 260))
        self._programs_map = {}

    def _programs_reload(self):
        items = self.app.programs_list()
        tree = self._programs_tree
        tree.delete(*tree.get_children())
        self._programs_map.clear()
        for it in items:
            iid = tree.insert("", tk.END, values=(
                it["name"], it["version"], it["publisher"]))
            self._programs_map[iid] = it
        self._programs_status.config(text=f"{len(items)} programas", fg=C_DIM)

    def _programs_uninstall(self):
        sel = self._programs_tree.selection()
        if not sel:
            self._programs_status.config(text="Selecione um programa.", fg=C_WARNING)
            return
        it = self._programs_map.get(sel[0])
        if not it:
            return
        if not messagebox.askyesno(
                "Desinstalar",
                f"Deseja desinstalar:\n\n{it['name']}\n\n"
                "O desinstalador do programa sera iniciado."):
            return
        ok, msg = self.app.program_uninstall(it)
        self._programs_status.config(text=msg, fg=C_SUCCESS if ok else C_DANGER)

    # ============================================================
    # PAGINA: SERVICOS
    # ============================================================
    def _build_page_services(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Servicos"] = page
        self._page_title(page, "Servicos",
                         "Servicos do Windows e seu controle")

        bar = tk.Frame(page, bg=C_CARD2, height=44)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        self._make_flat_btn(bar, "Recarregar",
                            self._services_reload).pack(side=tk.LEFT, padx=(10, 3), pady=8)
        self._make_accent_btn(bar, "Iniciar",
                              lambda: self._services_control("start")).pack(side=tk.LEFT, padx=3, pady=7)
        self._make_flat_btn(bar, "Parar",
                            lambda: self._services_control("stop")).pack(side=tk.LEFT, padx=3, pady=8)

        self._svc_start_mode = tk.StringVar(value="demand")
        ttk.Combobox(bar, textvariable=self._svc_start_mode,
                     values=["auto", "demand", "disabled"], state="readonly",
                     style="App.TCombobox", width=9, font=FONT_SMALL).pack(
                         side=tk.LEFT, padx=(12, 3), pady=9)
        self._make_flat_btn(bar, "Aplicar inicio",
                            lambda: self._services_control("config")).pack(side=tk.LEFT, padx=3, pady=8)

        self._services_status = tk.Label(bar, text="", bg=C_CARD2, fg=C_MUTED,
                                         font=FONT_SMALL)
        self._services_status.pack(side=tk.RIGHT, padx=10)

        self._services_tree = self._make_table(
            page, ("Servico", "Nome", "Status", "Inicio"),
            (300, 180, 90, 100))
        self._services_map = {}

    def _services_reload(self):
        items = self.app.services_list()
        tree = self._services_tree
        tree.delete(*tree.get_children())
        self._services_map.clear()
        for it in items:
            iid = tree.insert("", tk.END, values=(
                it["display"], it["name"], it["status"], it["start"]))
            self._services_map[iid] = it
        self._services_status.config(text=f"{len(items)} servicos", fg=C_DIM)

    def _services_control(self, op):
        sel = self._services_tree.selection()
        if not sel:
            self._services_status.config(text="Selecione um servico.", fg=C_WARNING)
            return
        it = self._services_map.get(sel[0])
        if not it:
            return
        name = it["name"]
        self._show_terminal_if_hidden()
        if op == "start":
            threading.Thread(target=self.app.service_start, args=(name,),
                             daemon=True).start()
        elif op == "stop":
            if not messagebox.askyesno("Parar servico",
                    f"Parar o servico '{it['display']}'?"):
                return
            threading.Thread(target=self.app.service_stop, args=(name,),
                             daemon=True).start()
        elif op == "config":
            mode = self._svc_start_mode.get()
            if mode == "disabled" and not messagebox.askyesno(
                    "Desabilitar servico",
                    f"Desabilitar a inicializacao de '{it['display']}'?"):
                return
            threading.Thread(target=self.app.service_set_start, args=(name, mode),
                             daemon=True).start()
        self._services_status.config(text="Comando enviado (veja o terminal).",
                                     fg=C_ACCENT)

    # ============================================================
    # PAGINA: DISCO (analisador estilo TreeSize)
    # ============================================================
    def _build_page_disk(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Disco"] = page
        self._page_title(page, "Disco",
                         "Analise de uso de espaco, maiores arquivos e duplicados")

        bar = tk.Frame(page, bg=C_CARD2, height=44)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        self._disk_path_var = tk.StringVar(
            value=os.environ.get("SystemDrive", "C:") + "\\")
        tk.Entry(bar, textvariable=self._disk_path_var,
                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", font=FONT_MONO).pack(
                     side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 4), pady=8, ipady=3)
        self._make_flat_btn(bar, "Pasta...",
                            self._browse_disk).pack(side=tk.LEFT, pady=8)
        self._make_accent_btn(bar, "Analisar",
                              self._disk_analyze).pack(side=tk.LEFT, padx=(4, 2), pady=7)

        bar2 = tk.Frame(page, bg=C_BG)
        bar2.pack(fill=tk.X, padx=8, pady=4)
        self._make_flat_btn(bar2, "Arvore de pastas",
                            lambda: self._disk_set_mode("tree")).pack(side=tk.LEFT, padx=(0, 4))
        self._make_flat_btn(bar2, "Maiores arquivos",
                            lambda: self._disk_set_mode("files")).pack(side=tk.LEFT, padx=4)
        self._make_flat_btn(bar2, "Localizar duplicados",
                            self._disk_duplicates).pack(side=tk.LEFT, padx=4)
        self._make_flat_btn(bar2, "Exportar relatorio",
                            self._disk_report).pack(side=tk.LEFT, padx=4)
        self._disk_status = tk.Label(bar2, text="Selecione uma pasta e clique Analisar.",
                                     bg=C_BG, fg=C_MUTED, font=FONT_SMALL)
        self._disk_status.pack(side=tk.RIGHT)

        wrap = tk.Frame(page, bg=C_BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        ysb = ttk.Scrollbar(wrap, orient="vertical",
                            style="App.Vertical.TScrollbar")
        self._disk_tree = ttk.Treeview(
            wrap, style="App.Treeview", show="tree headings",
            columns=("tamanho", "pct"), yscrollcommand=ysb.set)
        ysb.config(command=self._disk_tree.yview)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)
        self._disk_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._disk_tree.heading("#0", text="Pasta / Arquivo")
        self._disk_tree.heading("tamanho", text="Tamanho")
        self._disk_tree.heading("pct", text="%")
        self._disk_tree.column("#0", width=460, anchor="w")
        self._disk_tree.column("tamanho", width=110, anchor="e")
        self._disk_tree.column("pct", width=70, anchor="e")
        self._disk_tree.bind("<<TreeviewOpen>>", self._disk_on_open)

        self._disk_result = None
        self._disk_node_path = {}

    def _browse_disk(self):
        path = filedialog.askdirectory(title="Selecione a pasta/unidade para analisar")
        if path:
            self._disk_path_var.set(path)

    def _disk_analyze(self):
        root = self._disk_path_var.get().strip()
        if not root or not os.path.isdir(root):
            self._disk_status.config(text="Caminho invalido.", fg=C_DANGER)
            return
        self._disk_status.config(text="Analisando... (pode demorar)", fg=C_ACCENT)
        self._show_terminal_if_hidden()

        def _work():
            result = self.app.disk_scan(root)
            self.root.after(0, lambda: self._disk_done(result))

        threading.Thread(target=_work, daemon=True).start()

    def _disk_done(self, result):
        self._disk_result = result
        from app.disk_analyzer import human_size
        self._disk_status.config(
            text=f"Total: {human_size(result['total'])} em {result['n_files']} arquivos",
            fg=C_SUCCESS)
        self._disk_set_mode("tree")

    def _disk_set_mode(self, mode):
        if not self._disk_result:
            self._disk_status.config(text="Analise uma pasta primeiro.", fg=C_WARNING)
            return
        tree = self._disk_tree
        tree.delete(*tree.get_children())
        self._disk_node_path = {}
        from app.disk_analyzer import human_size

        if mode == "files":
            tree.heading("#0", text="Arquivo")
            tree.heading("tamanho", text="Tamanho")
            tree.heading("pct", text="")
            for size, fp in self._disk_result["largest"]:
                tree.insert("", tk.END, text=fp,
                            values=(human_size(size), ""))
            self._disk_status.config(
                text=f"{len(self._disk_result['largest'])} maiores arquivos",
                fg=C_DIM)
            return

        # modo arvore
        tree.heading("#0", text="Pasta / Arquivo")
        tree.heading("tamanho", text="Tamanho")
        tree.heading("pct", text="%")
        root = self._disk_result["root"]
        total = self._disk_result["total"] or 1
        riid = tree.insert("", tk.END, text=root, open=True,
                           values=(human_size(total), "100%"))
        self._disk_node_path[riid] = root
        self._disk_load_children(riid, root)
        tree.item(riid, open=True)

    def _disk_load_children(self, parent_iid, path):
        from app.disk_analyzer import human_size
        total = self._disk_result["total"] or 1
        for name, full, size, has_sub in self.app.disk_children(path):
            pct = size / total * 100
            iid = self._disk_tree.insert(
                parent_iid, tk.END, text=name,
                values=(human_size(size), f"{pct:.1f}%"))
            self._disk_node_path[iid] = full
            if has_sub:
                # filho fantasma para exibir a seta de expandir
                self._disk_tree.insert(iid, tk.END, text="...")

    def _disk_on_open(self, _event):
        iid = self._disk_tree.focus()
        path = self._disk_node_path.get(iid)
        if not path:
            return
        children = self._disk_tree.get_children(iid)
        # Se so tem o filho fantasma, carrega de verdade
        if len(children) == 1 and self._disk_tree.item(children[0], "text") == "...":
            self._disk_tree.delete(children[0])
            self._disk_load_children(iid, path)

    def _disk_duplicates(self):
        root = self._disk_path_var.get().strip()
        if not root or not os.path.isdir(root):
            self._disk_status.config(text="Caminho invalido.", fg=C_DANGER)
            return
        self._disk_status.config(text="Procurando duplicados...", fg=C_ACCENT)
        self._show_terminal_if_hidden()

        def _work():
            res = self.app.disk_find_duplicates(root)
            self.root.after(0, lambda: self._disk_show_dups(res))

        threading.Thread(target=_work, daemon=True).start()

    def _disk_show_dups(self, res):
        from app.disk_analyzer import human_size
        tree = self._disk_tree
        tree.delete(*tree.get_children())
        self._disk_node_path = {}
        tree.heading("#0", text="Arquivos duplicados")
        tree.heading("tamanho", text="Tamanho")
        tree.heading("pct", text="Copias")
        for g in res["groups"]:
            gid = tree.insert("", tk.END,
                              text=f"Grupo ({len(g['files'])} copias)",
                              values=(human_size(g["size"]), len(g["files"])))
            for fp in g["files"]:
                tree.insert(gid, tk.END, text=fp, values=("", ""))
        self._disk_status.config(
            text=f"{len(res['groups'])} grupos | recuperavel: {human_size(res['wasted'])}",
            fg=C_SUCCESS if res["groups"] else C_DIM)

    def _disk_report(self):
        if not self._disk_result:
            self._disk_status.config(text="Analise uma pasta primeiro.", fg=C_WARNING)
            return
        path = filedialog.asksaveasfilename(
            title="Salvar relatorio de disco", defaultextension=".html",
            filetypes=[("HTML", "*.html")], initialfile="relatorio_disco.html")
        if not path:
            return
        ok, msg = self.app.disk_report_html(self._disk_result, path)
        self._disk_status.config(text=msg, fg=C_SUCCESS if ok else C_DANGER)

    # ============================================================
    # PAGINA: EDITOR DE CODIGO (estilo Notepad++)
    # ============================================================
    def _build_page_editor(self):
        page = tk.Frame(self._content, bg=C_BG)
        self.pages["Editor"] = page
        self._page_title(page, "Editor",
                         "Abrir pasta/arquivo e editar com destaque de sintaxe")

        bar = tk.Frame(page, bg=C_CARD2, height=42)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        self._make_flat_btn(bar, "Abrir pasta",
                            self._ed_open_folder).pack(side=tk.LEFT, padx=(10, 3), pady=7)
        self._make_flat_btn(bar, "Abrir arquivo",
                            self._ed_open_file).pack(side=tk.LEFT, padx=3, pady=7)
        self._make_accent_btn(bar, "Salvar  (Ctrl+S)",
                              self._ed_save).pack(side=tk.LEFT, padx=3, pady=6)
        self._ed_info = tk.Label(bar, text="Nenhum arquivo aberto.",
                                 bg=C_CARD2, fg=C_MUTED, font=FONT_SMALL)
        self._ed_info.pack(side=tk.RIGHT, padx=10)

        pane = tk.Frame(page, bg=C_BG)
        pane.pack(fill=tk.BOTH, expand=True)

        # Arvore de arquivos
        left = tk.Frame(pane, bg=C_CARD2, width=230)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        tk.Label(left, text="Arquivos", bg=C_CARD2, fg=C_DIM, font=FONT_SMALL,
                 anchor="w", padx=10, pady=6).pack(fill=tk.X)
        tk.Frame(left, bg=C_BORDER, height=1).pack(fill=tk.X)
        ftree_wrap = tk.Frame(left, bg=C_CARD2)
        ftree_wrap.pack(fill=tk.BOTH, expand=True)
        fsb = ttk.Scrollbar(ftree_wrap, orient="vertical",
                            style="App.Vertical.TScrollbar")
        self._ed_tree = ttk.Treeview(ftree_wrap, style="App.Treeview",
                                     show="tree", yscrollcommand=fsb.set)
        fsb.config(command=self._ed_tree.yview)
        fsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._ed_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._ed_tree.bind("<<TreeviewOpen>>", self._ed_tree_expand)
        self._ed_tree.bind("<Double-1>", self._ed_tree_click)
        self._ed_node_path = {}

        tk.Frame(pane, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Area de edicao com numeros de linha
        right = tk.Frame(pane, bg=C_LOG_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._ed_lines = tk.Text(
            right, width=5, bg=C_PANEL, fg=C_MUTED, font=FONT_MONO,
            relief="flat", borderwidth=0, state="disabled",
            takefocus=0, highlightthickness=0)
        self._ed_lines.pack(side=tk.LEFT, fill=tk.Y)

        esb = ttk.Scrollbar(right, orient="vertical",
                            style="App.Vertical.TScrollbar")
        self._ed_text = tk.Text(
            right, bg=C_LOG_BG, fg=C_TEXT, insertbackground=C_TEXT,
            font=FONT_MONO, relief="flat", borderwidth=0, wrap="none",
            undo=True, highlightthickness=0, tabs="  ")
        esb.config(command=self._ed_yview)
        self._ed_text.config(yscrollcommand=self._ed_on_scroll)
        esb.pack(side=tk.RIGHT, fill=tk.Y)
        self._ed_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tags de sintaxe
        self._ed_text.tag_configure("kw",  foreground=C_SYN_KW)
        self._ed_text.tag_configure("str", foreground=C_SYN_STR)
        self._ed_text.tag_configure("com", foreground=C_SYN_COM)
        self._ed_text.tag_configure("num", foreground=C_SYN_NUM)
        self._ed_text.tag_configure("brk", foreground=C_SYN_BRK)

        self._ed_text.bind("<KeyRelease>", self._ed_on_key)
        self._ed_text.bind("<Control-s>", lambda e: (self._ed_save(), "break"))
        self._ed_text.bind("<MouseWheel>", self._ed_wheel)
        self._ed_lines.bind("<MouseWheel>", self._ed_wheel)

        self._ed_path = None
        self._ed_lang = (set(), "#", None, True)
        self._ed_hl_job = None

    # ---- sincronizacao de scroll / numeros de linha ----
    def _ed_yview(self, *args):
        self._ed_text.yview(*args)
        self._ed_lines.yview(*args)

    def _ed_on_scroll(self, first, last):
        # mantem a barra e os numeros alinhados
        self._ed_lines.yview_moveto(first)
        return

    def _ed_wheel(self, event):
        delta = int(-1 * (event.delta / 120))
        self._ed_text.yview_scroll(delta, "units")
        self._ed_lines.yview_scroll(delta, "units")
        return "break"

    def _ed_update_lines(self):
        total = int(self._ed_text.index("end-1c").split(".")[0])
        content = "\n".join(str(i) for i in range(1, total + 1))
        self._ed_lines.config(state="normal")
        self._ed_lines.delete("1.0", tk.END)
        self._ed_lines.insert("1.0", content)
        self._ed_lines.config(state="disabled")
        self._ed_lines.yview_moveto(self._ed_text.yview()[0])

    # ---- arvore de arquivos ----
    def _ed_open_folder(self, path=None):
        if path is None:
            path = filedialog.askdirectory(title="Abrir pasta no editor")
        if not path:
            return
        self._ed_tree.delete(*self._ed_tree.get_children())
        self._ed_node_path = {}
        root_id = self._ed_tree.insert("", tk.END, text=os.path.basename(path) or path,
                                       open=True)
        self._ed_node_path[root_id] = path
        self._ed_fill_tree(root_id, path)

    def _ed_fill_tree(self, parent_iid, path):
        try:
            entries = sorted(os.scandir(path),
                             key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    iid = self._ed_tree.insert(parent_iid, tk.END,
                                               text="\U0001f4c1 " + entry.name)
                    self._ed_node_path[iid] = entry.path
                    self._ed_tree.insert(iid, tk.END, text="...")  # fantasma
                else:
                    iid = self._ed_tree.insert(parent_iid, tk.END,
                                               text="  " + entry.name)
                    self._ed_node_path[iid] = entry.path
            except OSError:
                continue

    def _ed_tree_expand(self, _event):
        iid = self._ed_tree.focus()
        path = self._ed_node_path.get(iid)
        if not path or not os.path.isdir(path):
            return
        children = self._ed_tree.get_children(iid)
        if len(children) == 1 and self._ed_tree.item(children[0], "text") == "...":
            self._ed_tree.delete(children[0])
            self._ed_fill_tree(iid, path)

    def _ed_tree_click(self, _event):
        iid = self._ed_tree.focus()
        path = self._ed_node_path.get(iid)
        if path and os.path.isfile(path):
            self._ed_load(path)

    # ---- abrir / salvar ----
    def _ed_open_file(self):
        path = filedialog.askopenfilename(title="Abrir arquivo no editor")
        if path:
            self._ed_load(path)

    def _ed_load(self, path):
        content = None
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                with open(path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, OSError):
                continue
        if content is None:
            self._ed_info.config(text="Nao foi possivel abrir (binario?).", fg=C_DANGER)
            return
        self._ed_path = path
        ext = os.path.splitext(path)[1].lower()
        self._ed_lang = _LANG_MAP.get(ext, (_KW_CLIKE, "//", ("/*", "*/"), False))
        self._ed_text.delete("1.0", tk.END)
        self._ed_text.insert("1.0", content)
        self._ed_text.edit_reset()
        self._ed_update_lines()
        self._ed_highlight()
        lang = ext[1:].upper() if ext else "TXT"
        self._ed_info.config(text=f"{path}   [{lang}]", fg=C_DIM)

    def _ed_save(self):
        if not self._ed_path:
            path = filedialog.asksaveasfilename(title="Salvar como")
            if not path:
                return
            self._ed_path = path
        try:
            content = self._ed_text.get("1.0", "end-1c")
            with open(self._ed_path, "w", encoding="utf-8") as f:
                f.write(content)
            self._ed_info.config(text=f"Salvo: {self._ed_path}", fg=C_SUCCESS)
        except Exception as e:
            self._ed_info.config(text=f"Erro ao salvar: {e}", fg=C_DANGER)

    # ---- destaque de sintaxe ----
    def _ed_on_key(self, _event=None):
        self._ed_update_lines()
        if self._ed_hl_job:
            self.root.after_cancel(self._ed_hl_job)
        self._ed_hl_job = self.root.after(180, self._ed_highlight)

    def _ed_highlight(self):
        self._ed_hl_job = None
        text_widget = self._ed_text
        content = text_widget.get("1.0", "end-1c")
        if len(content) > 400_000:   # evita travar em arquivos enormes
            for t in ("kw", "str", "com", "num", "brk"):
                text_widget.tag_remove(t, "1.0", tk.END)
            return

        keywords, line_com, block, triple = self._ed_lang
        for t in ("kw", "str", "com", "num", "brk"):
            text_widget.tag_remove(t, "1.0", tk.END)

        def add(tag, start, end):
            text_widget.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")

        # 1) keywords, numeros, brackets
        if keywords:
            kw_re = r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b"
            for m in re.finditer(kw_re, content):
                add("kw", m.start(), m.end())
        for m in re.finditer(r"\b\d+(?:\.\d+)?\b", content):
            add("num", m.start(), m.end())
        for m in re.finditer(r"[()\[\]{}]", content):
            add("brk", m.start(), m.end())

        # 2) strings (sobrepoem kw/num/brk)
        patterns = []
        if triple:
            patterns.append(r'"""(?:.|\n)*?"""')
            patterns.append(r"'''(?:.|\n)*?'''")
        patterns.append(r'"(?:\\.|[^"\\\n])*"')
        patterns.append(r"'(?:\\.|[^'\\\n])*'")
        for pat in patterns:
            for m in re.finditer(pat, content):
                for t in ("kw", "num", "brk"):
                    text_widget.tag_remove(t, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
                add("str", m.start(), m.end())

        # 3) comentarios (sobrepoem tudo)
        com_spans = []
        if line_com:
            for m in re.finditer(re.escape(line_com) + r"[^\n]*", content):
                com_spans.append((m.start(), m.end()))
        if block:
            bpat = re.escape(block[0]) + r"(?:.|\n)*?" + re.escape(block[1])
            for m in re.finditer(bpat, content):
                com_spans.append((m.start(), m.end()))
        for s, e in com_spans:
            for t in ("kw", "num", "brk", "str"):
                text_widget.tag_remove(t, f"1.0+{s}c", f"1.0+{e}c")
            add("com", s, e)

    # ============================================================
    # TERMINAL DOCKADO (colapsavel)
    # ============================================================
    def _build_terminal_dock(self, parent):
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)

        dock = tk.Frame(parent, bg=C_BG)
        dock.pack(fill=tk.X, side=tk.BOTTOM)

        # Cabecalho do terminal (sempre visivel)
        hdr = tk.Frame(dock, bg=C_CARD2, height=32)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        self._term_toggle = tk.Label(
            hdr, text="▾  Terminal", bg=C_CARD2, fg=C_TEXT,
            font=FONT_SMALL, padx=10, cursor="hand2")
        self._term_toggle.pack(side=tk.LEFT, pady=6)
        self._term_toggle.bind("<Button-1>", lambda e: self._toggle_terminal())

        self._make_flat_btn(hdr, "Limpar",
                            self._clear_log).pack(side=tk.RIGHT, padx=8, pady=5)

        # Corpo do terminal (log + comando) com altura fixa
        self._term_body = tk.Frame(dock, bg=C_LOG_BG, height=240)
        self._term_body.pack(fill=tk.X)
        self._term_body.pack_propagate(False)

        self.log_box = scrolledtext.ScrolledText(
            self._term_body,
            bg=C_LOG_BG, fg=C_LOG_FG, font=FONT_MONO,
            state="disabled", relief="flat", borderwidth=0, wrap="none",
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)

        self.log_box.tag_configure("base",    foreground=C_LOG_FG)
        self.log_box.tag_configure("header",  foreground="#ffffff",
                                              font=("Consolas", 9, "bold"))
        self.log_box.tag_configure("info",    foreground="#60a8ff")
        self.log_box.tag_configure("ok",      foreground=C_SUCCESS)
        self.log_box.tag_configure("warn",    foreground=C_WARNING)
        self.log_box.tag_configure("error",   foreground=C_DANGER)
        self.log_box.tag_configure("denied",  foreground="#c060ff")
        self.log_box.tag_configure("section", foreground="#aaaacc",
                                              font=("Consolas", 9, "bold"))

        cmd_frame = tk.Frame(self._term_body, bg=C_CARD2, height=34)
        cmd_frame.pack(fill=tk.X, side=tk.BOTTOM)
        cmd_frame.pack_propagate(False)

        self._PLACEHOLDER = "Digite um comando (ex: ipconfig)"
        self.cmd_entry = tk.Entry(
            cmd_frame, bg=C_LOG_BG, fg=C_DIM,
            insertbackground=C_LOG_FG, font=FONT_MONO,
            relief="flat", borderwidth=0,
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)
        self.cmd_entry.insert(0, self._PLACEHOLDER)
        self.cmd_entry.bind("<FocusIn>",  self._cmd_focus_in)
        self.cmd_entry.bind("<FocusOut>", self._cmd_focus_out)
        self.cmd_entry.bind("<Return>",   self._send_command)
        self.cmd_entry.bind("<Tab>",      self._autocomplete)

        self._make_flat_btn(cmd_frame, "Enviar",
                            self._send_command).pack(side=tk.RIGHT, padx=8, pady=5)

    def _toggle_terminal(self):
        self._term_expanded = not self._term_expanded
        if self._term_expanded:
            self._term_body.pack(fill=tk.X)
            self._term_toggle.config(text="▾  Terminal")
        else:
            self._term_body.pack_forget()
            self._term_toggle.config(text="▸  Terminal")

    def _clear_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.config(state="disabled")

    # ============================================================
    # STATUS BAR
    # ============================================================
    def _build_statusbar(self):
        tk.Frame(self.root, bg=C_BORDER, height=1).pack(fill=tk.X)

        bar = tk.Frame(self.root, bg=C_CARD2, height=28)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        self.status_label = tk.Label(bar, text="Pronto", bg=C_CARD2,
                                     fg=C_DIM, font=FONT_SMALL, padx=10)
        self.status_label.pack(side=tk.LEFT, pady=4)

        self.progress = ttk.Progressbar(
            bar, style="App.Horizontal.TProgressbar",
            mode="indeterminate", length=160)
        self.progress.pack(side=tk.RIGHT, padx=10, pady=5)

    def progress_start(self, label="Executando..."):
        self.status_label.config(text=label[:60], fg=C_ACCENT)
        self.progress.start(12)

    def progress_stop(self):
        self.progress.stop()
        self.status_label.config(text="Pronto", fg=C_DIM)

    # ============================================================
    # POLLING DA FILA DE LOG
    # ============================================================
    def _poll_log_queue(self):
        try:
            for _ in range(50):
                msg = self.app.log_queue.get_nowait()
                self._append_log(msg)
        except Exception:
            pass
        self.root.after(40, self._poll_log_queue)

    def _classify_line(self, text):
        lower = text.lower()

        if "==" in text and len(text.strip()) > 4:
            stripped = text.strip()
            if stripped.startswith("=") or stripped.startswith("  >>"):
                return "header"

        if text.strip().startswith("--") and len(text.strip()) > 3:
            return "section"

        if any(k in lower for k in (
            "access denied", "acesso negado", "access is denied",
            "permissao negada", "permission denied", "5)", "error 5"
        )):
            return "denied"

        if any(k in lower for k in (
            "[erro]", "error", "failed", "falhou", "falha",
            "nao foi possivel", "could not", "cannot", "0x"
        )):
            return "error"

        if any(k in lower for k in (
            "[aviso]", "[atencao]", "warning", "aviso", "atencao",
            "deprecated", "obsoleto"
        )):
            return "warn"

        if any(k in lower for k in (
            "[ok]", "sucesso", "success", "concluido", "concluida",
            "finalizado", "completed", "100%", "repaired", "reparado",
            "no integrity violations"
        )):
            return "ok"

        if any(k in lower for k in (
            "[info]", "informacao", "iniciando", "iniciado", "starting",
            "passo ", "sequencia"
        )):
            return "info"

        return "base"

    def _append_log(self, text):
        self.log_box.config(state="normal")
        tag = self._classify_line(text)
        self.log_box.insert("end", text + "\n", tag)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def add_log(self, text):
        self._append_log(text)

    # ============================================================
    # TERMINAL: comando customizado
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
        if not self._term_expanded:
            self._toggle_terminal()
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
        btn = tk.Label(parent, text=text, bg=C_CARD, fg=C_TEXT,
                       font=FONT_SMALL, padx=10, pady=3,
                       cursor="hand2", relief="flat")
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>",    lambda e: btn.config(bg=C_HOVER))
        btn.bind("<Leave>",    lambda e: btn.config(bg=C_CARD))
        return btn

    def _make_accent_btn(self, parent, text, command):
        btn = tk.Label(parent, text=text, bg=C_ACCENT, fg="white",
                       font=FONT_SMALL, padx=12, pady=3,
                       cursor="hand2", relief="flat")
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>",    lambda e: btn.config(bg=C_ACCENT2))
        btn.bind("<Leave>",    lambda e: btn.config(bg=C_ACCENT))
        return btn
