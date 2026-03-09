import sys
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from collections import defaultdict

from config import ACTIONS, AUTOCOMPLETE_COMMANDS, VERSION_SOFTWARE, GROUPS_FILE, DEFAULT_GROUPS

# ============================================================
# PALETA DE CORES
# ============================================================
C_BG      = "#18181f"
C_PANEL   = "#101018"
C_CARD    = "#22222e"
C_CARD2   = "#1c1c28"
C_HOVER   = "#2a2a3a"
C_BORDER  = "#2e2e3e"
C_ACCENT  = "#4a80ff"
C_ACCENT2 = "#3060cc"
C_TEXT    = "#d8d8e8"
C_DIM     = "#6868a0"
C_SUCCESS = "#48d890"
C_WARNING = "#f0a040"
C_DANGER  = "#e85050"
C_LOG_BG  = "#0c0c14"
C_LOG_FG  = "#38d060"

FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_NORM  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 9)
FONT_GRP   = ("Segoe UI", 9, "bold")


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

        # Vincula scroll do mouse no canvas e nos filhos ja criados
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
# ============================================================
class GUI:

    def __init__(self, root, app):
        self.root = root
        self.app  = app

        self.autocomplete_index = 0
        self.check_vars = {}       # action_idx -> BooleanVar (aba Acoes)
        self.group_check_vars = {} # action_idx -> BooleanVar (editor de grupo)

        self._setup_window()
        self._apply_theme()
        self._build_header()
        self._build_body()
        self._build_statusbar()

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
    # TEMA TTK
    # ============================================================
    def _apply_theme(self):
        style = ttk.Style(self.root)
        style.theme_use("default")

        style.configure("App.TNotebook",
            background=C_PANEL, borderwidth=0, tabmargins=0)
        style.configure("App.TNotebook.Tab",
            background=C_CARD2, foreground=C_DIM,
            font=FONT_NORM, padding=[14, 6], borderwidth=0)
        style.map("App.TNotebook.Tab",
            background=[("selected", C_BG), ("active", C_HOVER)],
            foreground=[("selected", C_TEXT), ("active", C_TEXT)])

        style.configure("App.Vertical.TScrollbar",
            troughcolor=C_CARD, background=C_BORDER,
            borderwidth=0, arrowsize=10)

        style.configure("App.Horizontal.TProgressbar",
            troughcolor=C_CARD2, background=C_ACCENT, borderwidth=0)

    # ============================================================
    # HEADER
    # ============================================================
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C_PANEL, height=46)
        hdr.pack(side=tk.TOP, fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="Sek Optimize", bg=C_PANEL, fg=C_ACCENT,
                 font=FONT_TITLE).pack(side=tk.LEFT, padx=16, pady=10)
        tk.Label(hdr, text=f"v{VERSION_SOFTWARE}", bg=C_PANEL, fg=C_DIM,
                 font=FONT_SMALL).pack(side=tk.LEFT, pady=10)

        tk.Frame(self.root, bg=C_BORDER, height=1).pack(fill=tk.X)

    # ============================================================
    # CORPO
    # ============================================================
    def _build_body(self):
        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True)

        self._build_left_panel(body)
        tk.Frame(body, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)
        self._build_log_panel(body)

    # ============================================================
    # PAINEL ESQUERDO: abas no topo
    # ============================================================
    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg=C_BG, width=430)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        nb = ttk.Notebook(left, style="App.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True)

        tab_acoes  = tk.Frame(nb, bg=C_BG)
        tab_grupos = tk.Frame(nb, bg=C_BG)

        nb.add(tab_acoes,  text="  Acoes  ")
        nb.add(tab_grupos, text="  Grupos  ")

        self._build_tab_acoes(tab_acoes)
        self._build_tab_grupos(tab_grupos)

        nb.bind("<<NotebookTabChanged>>", lambda e: (
            self._refresh_groups_list()
            if nb.index(nb.select()) == 1 else None
        ))

    # ============================================================
    # ABA: ACOES
    # ============================================================
    def _build_tab_acoes(self, parent):

        toolbar = tk.Frame(parent, bg=C_CARD2, height=42)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        self._make_flat_btn(toolbar, "Selecionar Tudo",
                            self._check_all).pack(side=tk.LEFT, padx=(8, 3), pady=8)
        self._make_flat_btn(toolbar, "Limpar",
                            self._uncheck_all).pack(side=tk.LEFT, padx=3, pady=8)
        self._make_accent_btn(toolbar, "Executar Selecionados",
                              self._execute_checked).pack(side=tk.RIGHT, padx=8, pady=8)

        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)

        desc_outer = tk.Frame(parent, bg=C_CARD2, height=68)
        desc_outer.pack(fill=tk.X)
        desc_outer.pack_propagate(False)

        self.desc_label = tk.Label(
            desc_outer,
            text="Passe o mouse sobre uma acao para ver a descricao.",
            bg=C_CARD2, fg=C_DIM, font=FONT_SMALL,
            anchor="nw", justify="left", wraplength=400,
            padx=10, pady=6,
        )
        self.desc_label.pack(fill=tk.BOTH, expand=True)

        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)

        self._scroll_acoes = ScrollableFrame(parent, bg=C_CARD)
        self._scroll_acoes.pack(fill=tk.BOTH, expand=True)

        self._populate_acoes()

    def _populate_acoes(self):
        inner = self._scroll_acoes.inner
        for w in inner.winfo_children():
            w.destroy()
        self.check_vars.clear()

        groups = defaultdict(list)
        for idx, action in ACTIONS.items():
            groups[action["tab"]].append(idx)

        for group_name in sorted(groups.keys()):
            indices = sorted(groups[group_name])

            grp_hdr = tk.Frame(inner, bg=C_CARD2)
            grp_hdr.pack(fill=tk.X, pady=(6, 0))
            self._scroll_acoes._bind_scroll(grp_hdr)

            tk.Label(grp_hdr, text=f"  {group_name}", bg=C_CARD2,
                     fg=C_ACCENT, font=FONT_GRP,
                     anchor="w", pady=4).pack(fill=tk.X)
            self._scroll_acoes._bind_scroll(grp_hdr.winfo_children()[-1])

            tk.Frame(inner, bg=C_BORDER, height=1).pack(fill=tk.X)

            for idx in indices:
                action = ACTIONS[idx]
                var = tk.BooleanVar(value=False)
                self.check_vars[idx] = var
                color = C_WARNING if action["danger"] else C_TEXT

                row = tk.Frame(inner, bg=C_CARD, cursor="hand2")
                row.pack(fill=tk.X)
                self._scroll_acoes._bind_scroll(row)

                chk = tk.Checkbutton(
                    row, variable=var,
                    bg=C_CARD, activebackground=C_HOVER,
                    fg=color, selectcolor=C_CARD2,
                    highlightthickness=0, borderwidth=0, relief="flat",
                )
                chk.pack(side=tk.LEFT, padx=(8, 2), pady=3)
                self._scroll_acoes._bind_scroll(chk)

                lbl = tk.Label(row, text=action["label"], bg=C_CARD,
                               fg=color, font=FONT_NORM, anchor="w")
                lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=3)
                self._scroll_acoes._bind_scroll(lbl)

                # Clique no label = toggle checkbox
                lbl.bind("<Button-1>", lambda e, v=var: v.set(not v.get()))

                # Hover: muda fundo e mostra descricao
                desc = action.get("description", "")
                danger = action.get("danger", False)

                def _enter(e, r=row, c=chk, d=desc, dng=danger):
                    r.config(bg=C_HOVER)
                    c.config(bg=C_HOVER)
                    self.desc_label.config(
                        text=d, fg=C_WARNING if dng else C_TEXT)

                def _leave(e, r=row, c=chk):
                    r.config(bg=C_CARD)
                    c.config(bg=C_CARD)

                for w in (row, lbl, chk):
                    w.bind("<Enter>", _enter)
                    w.bind("<Leave>", _leave)

    def _check_all(self):
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
    # ABA: GRUPOS
    # Grupos padrao vem de DEFAULT_GROUPS (codigo).
    # Grupos customizados sao salvos em JSON.
    # ============================================================
    def _build_tab_grupos(self, parent):
        # Carrega grupos customizados do JSON
        self._custom_groups = self._load_custom_groups()

        toolbar = tk.Frame(parent, bg=C_CARD2, height=42)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        self._make_flat_btn(toolbar, "Novo Grupo",
                            self._new_group).pack(side=tk.LEFT, padx=(8, 3), pady=8)
        self._make_flat_btn(toolbar, "Excluir",
                            self._delete_group).pack(side=tk.LEFT, padx=3, pady=8)
        self._make_flat_btn(toolbar, "Exportar",
                            self._export_groups).pack(side=tk.LEFT, padx=3, pady=8)
        self._make_flat_btn(toolbar, "Importar",
                            self._import_groups).pack(side=tk.LEFT, padx=3, pady=8)
        self._make_accent_btn(toolbar, "Executar Grupo",
                              self._run_group).pack(side=tk.RIGHT, padx=8, pady=8)

        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)

        pane = tk.Frame(parent, bg=C_BG)
        pane.pack(fill=tk.BOTH, expand=True)

        # Lista de grupos
        list_frame = tk.Frame(pane, bg=C_CARD2, width=160)
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

        # Editor
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

        # Label indica se o grupo e padrao (nao editavel) ou customizado
        self._group_type_label = tk.Label(
            name_frame, text="", bg=C_CARD2, fg=C_DIM, font=FONT_SMALL)
        self._group_type_label.pack(side=tk.LEFT, padx=4)

        self._btn_salvar = self._make_flat_btn(
            name_frame, "Salvar", self._save_group)
        self._btn_salvar.pack(side=tk.RIGHT, padx=8, pady=6)

        tk.Frame(edit_outer, bg=C_BORDER, height=1).pack(fill=tk.X)

        tk.Label(edit_outer,
                 text="Acoes do grupo:",
                 bg=C_BG, fg=C_DIM, font=FONT_SMALL,
                 anchor="w", padx=10, pady=5).pack(fill=tk.X)

        self._scroll_grupos = ScrollableFrame(edit_outer, bg=C_CARD)
        self._scroll_grupos.pack(fill=tk.BOTH, expand=True)

        self._current_group_is_builtin = False
        self._populate_group_editor()

    def _all_groups(self):
        """Retorna dicionario unificado: padrao primeiro, customizados depois."""
        merged = {}
        for name, data in DEFAULT_GROUPS.items():
            merged[name] = data
        for name, data in self._custom_groups.items():
            merged[name] = data
        return merged

    def _populate_group_editor(self, preset_indices=None, readonly=False):
        preset = set(preset_indices or [])
        inner = self._scroll_grupos.inner
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
                var = tk.BooleanVar(value=(idx in preset))
                self.group_check_vars[idx] = var
                color = C_WARNING if action["danger"] else C_TEXT

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
        name = self.groups_listbox.get(sel[0])
        all_g = self._all_groups()
        group = all_g.get(name, {})
        is_builtin = group.get("builtin", False)

        self._current_group_is_builtin = is_builtin
        self.group_name_var.set(name)
        self._group_name_entry.config(state="disabled" if is_builtin else "normal")
        self._btn_salvar.config(fg=C_DIM if is_builtin else C_TEXT,
                                cursor="arrow" if is_builtin else "hand2")
        self._group_type_label.config(
            text="(padrao)" if is_builtin else "(customizado)",
            fg=C_DIM)

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
            messagebox.showwarning("Grupo vazio",
                "Selecione ao menos uma acao.")
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
            # Filtra apenas entradas com "actions" como lista de inteiros
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
            messagebox.showinfo("Importado",
                f"{len(valid)} grupo(s) importado(s).")
        except Exception as e:
            messagebox.showerror("Erro ao importar", str(e))

    # ============================================================
    # PERSISTENCIA DE GRUPOS CUSTOMIZADOS
    # ============================================================
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
    # PAINEL DE LOG
    # ============================================================
    def _build_log_panel(self, parent):
        log_outer = tk.Frame(parent, bg=C_BG)
        log_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_hdr = tk.Frame(log_outer, bg=C_CARD2, height=36)
        log_hdr.pack(fill=tk.X)
        log_hdr.pack_propagate(False)

        tk.Label(log_hdr, text="Log de Execucao", bg=C_CARD2, fg=C_DIM,
                 font=FONT_SMALL, padx=10).pack(side=tk.LEFT, pady=8)
        self._make_flat_btn(log_hdr, "Limpar",
                            self._clear_log).pack(side=tk.RIGHT, padx=8, pady=6)

        tk.Frame(log_outer, bg=C_BORDER, height=1).pack(fill=tk.X)

        self.log_box = scrolledtext.ScrolledText(
            log_outer,
            bg=C_LOG_BG, fg=C_LOG_FG, font=FONT_MONO,
            state="disabled", relief="flat", borderwidth=0, wrap="none",
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)

        # --------------------------------------------------------
        # TAGS DE CORES DO TERMINAL
        # Prioridade: palavras-chave na linha definem a cor
        # --------------------------------------------------------
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

        tk.Frame(log_outer, bg=C_BORDER, height=1).pack(fill=tk.X)

        cmd_frame = tk.Frame(log_outer, bg=C_CARD2, height=36)
        cmd_frame.pack(fill=tk.X)
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
                            self._send_command).pack(side=tk.RIGHT, padx=8, pady=6)

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
            mode="indeterminate", length=160,
        )
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
        """
        Determina a tag de cor da linha com base em palavras-chave.
        Ordem: mais especifico primeiro.
        """
        lower = text.lower()

        # Cabecalhos gerados por log_title (linhas com == ou >>)
        if "==" in text and len(text.strip()) > 4:
            stripped = text.strip()
            if stripped.startswith("=") or stripped.startswith("  >>"):
                return "header"

        # Separador de secao (linhas com --)
        if text.strip().startswith("--") and len(text.strip()) > 3:
            return "section"

        # Permissao negada (varios idiomas / codigos comuns)
        if any(k in lower for k in (
            "access denied", "acesso negado", "access is denied",
            "permissao negada", "permission denied", "5)", "error 5"
        )):
            return "denied"

        # Erros
        if any(k in lower for k in (
            "[erro]", "error", "failed", "falhou", "falha",
            "nao foi possivel", "could not", "cannot", "0x"
        )):
            return "error"

        # Avisos / warnings
        if any(k in lower for k in (
            "[aviso]", "[atencao]", "warning", "aviso", "atencao",
            "deprecated", "obsoleto"
        )):
            return "warn"

        # Sucesso / ok
        if any(k in lower for k in (
            "[ok]", "sucesso", "success", "concluido", "concluida",
            "finalizado", "completed", "100%", "repaired", "reparado",
            "no integrity violations"
        )):
            return "ok"

        # Informacao
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
    # TERMINAL
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