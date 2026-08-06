"""
Ferramenta standalone: gera um relatorio HTML (sidebar + conteudo) a
partir de:
  - um unico arquivo JSON exportado pelo Sek Optimize; ou
  - uma pasta contendo varios desses arquivos JSON, gerando um unico
    HTML consolidado com navegacao por maquina.

Uso: python util/json_to_html.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from tkinter import Tk, filedialog, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from util.report_html import render_report, render_consolidated


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _export_single(json_path):
    data     = _load_json(json_path)
    html     = render_report(data)
    hostname = data.get("system", {}).get("hostname", "relatorio")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = Path(json_path).parent / f"{hostname}_{timestamp}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _export_folder(folder_path):
    folder  = Path(folder_path)
    entries = []

    for file in sorted(folder.glob("*.json")):
        try:
            data = _load_json(file)
            entries.append((file.stem, data))
            print(f"[OK] {file.name}")
        except Exception as e:
            print(f"[ERRO] {file.name} -> {e}")

    if not entries:
        raise SystemExit("Nenhum JSON valido encontrado na pasta.")

    html      = render_consolidated(entries)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = folder / f"relatorio_consolidado_{timestamp}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path, len(entries)


def main():
    Tk().withdraw()

    is_folder = messagebox.askyesno(
        "Sek Optimize - Exportar HTML",
        "Deseja gerar um relatorio CONSOLIDADO a partir de uma pasta com "
        "varios arquivos JSON?\n\n"
        "Sim = selecionar uma pasta\n"
        "Nao = selecionar um unico arquivo JSON",
    )

    try:
        if is_folder:
            folder_path = filedialog.askdirectory(
                title="Selecione a pasta com os arquivos JSON"
            )
            if not folder_path:
                raise SystemExit("Nenhuma pasta selecionada.")

            out_path, count = _export_folder(folder_path)

            print()
            print("=" * 50)
            print(f"HTML CONSOLIDADO EXPORTADO ({count} maquina(s))")
            print(out_path)
            print("=" * 50)
            print()

            messagebox.showinfo(
                "Concluido", f"Relatorio consolidado gerado:\n{out_path}"
            )
        else:
            json_path = filedialog.askopenfilename(
                title="Selecione o JSON", filetypes=[("JSON", "*.json")]
            )
            if not json_path:
                raise SystemExit("Nenhum arquivo selecionado.")

            out_path = _export_single(json_path)

            print()
            print("=" * 50)
            print("HTML EXPORTADO COM SUCESSO")
            print(out_path)
            print("=" * 50)
            print()

            messagebox.showinfo("Concluido", f"Relatorio gerado:\n{out_path}")

    except SystemExit as e:
        if str(e):
            messagebox.showwarning("Cancelado", str(e))
    except Exception as e:
        messagebox.showerror("Erro", str(e))


if __name__ == "__main__":
    main()
