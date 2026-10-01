import os
import hashlib
from datetime import datetime

from app.app import App


def human_size(n):
    """Formata bytes em unidade legivel."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if n < 1024 or unit == "PB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


class DiskAnalyzer(App):
    """
    Analisador de uso de disco estilo TreeSize.

    - Varre uma pasta somando o tamanho de cada subpasta (bottom-up).
    - Lista os maiores arquivos.
    - Localiza arquivos duplicados (mesmo tamanho + mesmo hash).
    - Gera relatorio HTML.
    """

    def __init__(self):
        super().__init__()
        self._disk_sizes = {}   # dirpath -> tamanho total (cache do ultimo scan)

    # ============================================================
    # VARREDURA (bottom-up: subpastas antes do pai)
    # ============================================================
    def disk_scan(self, root):
        self.log_title("Analise de Disco")
        self.log_info(f"Varrendo: {root}")
        t0 = datetime.now()
        sizes = {}
        largest = []
        n_files = 0
        n_errors = 0

        def _onerror(_e):
            nonlocal n_errors
            n_errors += 1

        for dirpath, dirnames, filenames in os.walk(root, topdown=False,
                                                    onerror=_onerror):
            total = 0
            for fn in filenames:
                try:
                    fp = os.path.join(dirpath, fn)
                    s = os.path.getsize(fp)
                except OSError:
                    n_errors += 1
                    continue
                total += s
                n_files += 1
                largest.append((s, fp))
            for d in dirnames:
                total += sizes.get(os.path.join(dirpath, d), 0)
            sizes[dirpath] = total

        largest.sort(key=lambda t: t[0], reverse=True)
        self._disk_sizes = sizes
        dur = (datetime.now() - t0).total_seconds()
        total_size = sizes.get(root, 0)
        self.log_ok(
            f"Concluido: {human_size(total_size)} em {n_files} arquivos "
            f"({dur:.1f}s, {n_errors} itens sem acesso).")
        self.log_sep()
        return {
            "root": root,
            "total": total_size,
            "largest": largest[:200],
            "n_files": n_files,
            "n_errors": n_errors,
            "duration": dur,
        }

    def disk_children(self, path):
        """Subpastas imediatas com tamanho (do cache), ordenadas por tamanho."""
        out = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            full = entry.path
                            size = self._disk_sizes.get(full, 0)
                            has_sub = self._has_subdir(full)
                            out.append((entry.name, full, size, has_sub))
                    except OSError:
                        continue
        except OSError:
            return []
        out.sort(key=lambda t: t[2], reverse=True)
        return out

    @staticmethod
    def _has_subdir(path):
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            return True
                    except OSError:
                        continue
        except OSError:
            pass
        return False

    # ============================================================
    # DUPLICADOS (mesmo tamanho + mesmo hash)
    # ============================================================
    def disk_find_duplicates(self, root, min_size=1024 * 1024):
        self.log_title("Localizar Duplicados")
        self.log_info(f"Pasta: {root}  (ignorando arquivos < {human_size(min_size)})")
        by_size = {}
        for dirpath, _dirs, files in os.walk(root, onerror=lambda e: None):
            for fn in files:
                try:
                    fp = os.path.join(dirpath, fn)
                    s = os.path.getsize(fp)
                except OSError:
                    continue
                if s >= min_size:
                    by_size.setdefault(s, []).append(fp)

        groups = []
        wasted = 0
        for size, paths in by_size.items():
            if len(paths) < 2:
                continue
            by_hash = {}
            for fp in paths:
                h = self._hash_file(fp)
                if h:
                    by_hash.setdefault(h, []).append(fp)
            for _h, dups in by_hash.items():
                if len(dups) > 1:
                    groups.append({"size": size, "files": dups})
                    wasted += size * (len(dups) - 1)

        groups.sort(key=lambda g: g["size"] * (len(g["files"]) - 1), reverse=True)
        self.log_ok(f"{len(groups)} grupo(s) de duplicados. "
                    f"Espaco recuperavel: {human_size(wasted)}.")
        self.log_sep()
        return {"groups": groups, "wasted": wasted}

    @staticmethod
    def _hash_file(path, chunk=1024 * 1024):
        try:
            h = hashlib.md5()
            with open(path, "rb") as f:
                while True:
                    block = f.read(chunk)
                    if not block:
                        break
                    h.update(block)
            return h.hexdigest()
        except OSError:
            return None

    # ============================================================
    # RELATORIO HTML
    # ============================================================
    def disk_report_html(self, result, path):
        root = result.get("root", "")
        total = result.get("total", 0)
        largest = result.get("largest", [])
        children = self.disk_children(root)

        def rows_dirs():
            out = []
            for name, _full, size, _hs in children[:50]:
                pct = (size / total * 100) if total else 0
                out.append(
                    f"<tr><td>{_esc(name)}</td><td class='r'>{human_size(size)}</td>"
                    f"<td class='r'>{pct:.1f}%</td></tr>")
            return "\n".join(out)

        def rows_files():
            out = []
            for size, fp in largest[:100]:
                out.append(
                    f"<tr><td>{_esc(fp)}</td><td class='r'>{human_size(size)}</td></tr>")
            return "\n".join(out)

        html = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<title>Relatorio de Disco - {_esc(root)}</title>
<style>
 body{{background:#15151c;color:#d8d8e8;font-family:Segoe UI,Arial,sans-serif;margin:24px}}
 h1{{color:#4a80ff;font-size:20px}} h2{{color:#48d890;font-size:15px;margin-top:28px}}
 .meta{{color:#7676a8;font-size:13px;margin-bottom:8px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 th,td{{text-align:left;padding:6px 10px;border-bottom:1px solid #2b2b3a}}
 th{{color:#4a80ff}} td.r,th.r{{text-align:right}}
 tr:hover td{{background:#20202c}}
</style></head><body>
<h1>Relatorio de Uso de Disco</h1>
<div class="meta">Pasta analisada: {_esc(root)}<br>
Tamanho total: {human_size(total)} &middot; {result.get('n_files',0)} arquivos &middot;
Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</div>
<h2>Maiores subpastas</h2>
<table><tr><th>Pasta</th><th class="r">Tamanho</th><th class="r">% do total</th></tr>
{rows_dirs()}</table>
<h2>Maiores arquivos</h2>
<table><tr><th>Arquivo</th><th class="r">Tamanho</th></tr>
{rows_files()}</table>
</body></html>"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self.log_ok(f"Relatorio de disco salvo: {path}")
            return True, f"Relatorio salvo: {os.path.basename(path)}"
        except Exception as e:
            return False, str(e)


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))
