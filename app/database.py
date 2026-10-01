import os
import sqlite3

from app.app import App


class Database(App):
    """
    Leitor/executor de bancos SQLite (.db / .sqlite / .sqlite3).

    A conexao fica guardada na instancia; a GUI chama os metodos
    de forma sincrona (SQLite e rapido) e renderiza o resultado em grade.
    Consultas que nao sao SELECT sao efetivadas com commit.
    """

    def __init__(self):
        super().__init__()
        self._db_conn = None
        self._db_path = None

    # ============================================================
    # CONEXAO
    # ============================================================
    def db_connect(self, path):
        """Abre o arquivo SQLite. Retorna (ok: bool, mensagem: str)."""
        self.db_close()
        if not os.path.isfile(path):
            return False, "Arquivo nao encontrado."
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            # Valida que e mesmo um banco SQLite legivel
            conn.execute("SELECT name FROM sqlite_master LIMIT 1")
            self._db_conn = conn
            self._db_path = path
            self.log_title("Banco de Dados")
            self.log_ok(f"Conectado: {path}")
            tabelas = self.db_tables()
            self.log_info(f"{len(tabelas)} tabela(s): {', '.join(tabelas) or '(nenhuma)'}")
            return True, f"Conectado ({len(tabelas)} tabelas)."
        except sqlite3.DatabaseError as e:
            return False, f"Arquivo invalido ou nao e um banco SQLite: {e}"
        except Exception as e:
            return False, str(e)

    def db_close(self):
        if self._db_conn:
            try:
                self._db_conn.close()
            except Exception:
                pass
        self._db_conn = None
        self._db_path = None

    def db_is_open(self):
        return self._db_conn is not None

    # ============================================================
    # METADADOS
    # ============================================================
    def db_tables(self):
        """Lista tabelas e views do banco."""
        if not self._db_conn:
            return []
        cur = self._db_conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        return [r[0] for r in cur.fetchall()]

    def db_row_count(self, table):
        """Conta linhas de uma tabela (nome entre aspas para seguranca)."""
        if not self._db_conn:
            return 0
        try:
            safe = '"' + table.replace('"', '""') + '"'
            cur = self._db_conn.execute(f"SELECT COUNT(*) FROM {safe}")
            return cur.fetchone()[0]
        except Exception:
            return 0

    # ============================================================
    # EXECUCAO DE CONSULTAS
    # ============================================================
    def db_query(self, sql):
        """
        Executa uma instrucao SQL.
        Retorna dict:
          ok=True  -> {ok, columns, rows, info}
          ok=False -> {ok, error}
        Para instrucoes que nao retornam linhas (INSERT/UPDATE/...),
        columns/rows ficam vazios e info traz as linhas afetadas.
        """
        if not self._db_conn:
            return {"ok": False, "error": "Nenhum banco aberto."}
        sql = sql.strip()
        if not sql:
            return {"ok": False, "error": "Consulta vazia."}
        try:
            cur = self._db_conn.execute(sql)
            if cur.description:
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
                rows = [tuple(r) for r in rows]
                return {
                    "ok": True,
                    "columns": columns,
                    "rows": rows,
                    "info": f"{len(rows)} linha(s) retornada(s).",
                }
            else:
                self._db_conn.commit()
                n = cur.rowcount
                return {
                    "ok": True,
                    "columns": [],
                    "rows": [],
                    "info": f"OK. {n} linha(s) afetada(s)." if n >= 0 else "OK.",
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ============================================================
    # EXPORTACAO DO RESULTADO (CSV / XLSX)
    # ============================================================
    def db_export(self, columns, rows, path, fmt):
        """Exporta colunas/linhas para CSV ou XLSX. Retorna (ok, mensagem)."""
        if not columns:
            return False, "Nada para exportar (execute um SELECT primeiro)."
        try:
            if fmt == "csv":
                import csv
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(columns)
                    for r in rows:
                        w.writerow(["" if v is None else v for v in r])
            elif fmt == "xlsx":
                from openpyxl import Workbook
                wb = Workbook()
                ws = wb.active
                ws.title = "Consulta"
                ws.append(list(columns))
                for r in rows:
                    ws.append(["" if v is None else v for v in r])
                wb.save(path)
            else:
                return False, f"Formato invalido: {fmt}"
            self.log_ok(f"Resultado exportado ({len(rows)} linhas): {path}")
            return True, f"Exportado: {os.path.basename(path)}"
        except Exception as e:
            return False, str(e)
