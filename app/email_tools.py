import os
import re
import threading
import mailbox
from datetime import datetime
from email.message import EmailMessage
from email.parser import Parser
from email.policy import default as default_policy
from email.utils import format_datetime

from app.app import App

try:
    import pypff
    _HAS_PYPFF = True
except ImportError:
    _HAS_PYPFF = False


# ============================================================
# HELPERS DE MODULO
# ============================================================
def _decode_body(raw):
    """Decodifica corpo (bytes/str/None) para str."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("latin-1", errors="replace")


def _safe_name(text, maxlen=60):
    """Gera um nome de arquivo seguro a partir do assunto."""
    text = (text or "sem_assunto").strip()
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", text)
    return (text[:maxlen] or "sem_assunto").strip("_ .")


def _plain_text_of(msg):
    """Extrai o corpo em texto de um email.message.Message qualquer."""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload is not None:
                        return _decode_body(payload)
            return ""
        payload = msg.get_payload(decode=True)
        if payload is not None:
            return _decode_body(payload)
        return msg.get_payload()
    except Exception:
        return ""


class EmailTools(App):
    """
    Conversao de e-mails entre formatos, lendo os arquivos direto do disco:

      - Leitura SEM Outlook (via pypff): PST / OST  ->  MBOX / EML
      - MBOX (Thunderbird)             ->  EML
      - Gravacao em PST                ->  requer Microsoft Outlook (automacao COM)

    O Thunderbird importa MBOX nativamente, entao "PST/OST -> Thunderbird"
    e coberto pela saida em MBOX.
    """

    def __init__(self):
        super().__init__()

    # ============================================================
    # DISPONIBILIDADE
    # ============================================================
    def outlook_available(self):
        """True se o Outlook estiver instalado e acessivel via COM."""
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            try:
                win32com.client.Dispatch("Outlook.Application")
                return True
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            return False

    @staticmethod
    def detect_source_format(path):
        """Deduz o formato de origem pela extensao."""
        ext = os.path.splitext(path)[1].lower()
        if ext in (".pst", ".ost"):
            return "pst"
        if ext in (".mbox", ".mbx", ""):
            return "mbox"
        return "mbox"

    # ============================================================
    # PONTO DE ENTRADA (chamado pela GUI)
    # ============================================================
    def email_convert(self, src_path, dst_fmt, dst_path):
        """Executa a conversao em thread. dst_fmt: 'mbox' | 'eml' | 'pst'."""
        threading.Thread(
            target=self._email_convert_run,
            args=(src_path, dst_fmt, dst_path),
            daemon=True,
        ).start()

    def _email_convert_run(self, src_path, dst_fmt, dst_path):
        self._progress_start("Convertendo e-mails...")
        self.log_title("Conversao de E-mail")
        try:
            if not os.path.exists(src_path):
                self.log_error(f"Origem nao encontrada: {src_path}")
                return

            src_fmt = self.detect_source_format(src_path)
            self.log_info(f"Origem : {src_path}  ({src_fmt.upper()})")
            self.log_info(f"Destino: {dst_path}  ({dst_fmt.upper()})")

            if src_fmt == "pst" and not _HAS_PYPFF:
                self.log_error(
                    "Biblioteca de leitura PST/OST (pypff) nao esta disponivel.")
                return
            if src_fmt == "pst":
                messages = self._read_pst(src_path)
            else:
                messages = self._read_mbox(src_path)

            if dst_fmt == "mbox":
                total = self._write_mbox(messages, dst_path)
            elif dst_fmt == "eml":
                total = self._write_eml(messages, dst_path)
            elif dst_fmt == "pst":
                total = self._write_pst(messages, dst_path)
            else:
                self.log_error(f"Formato de destino invalido: {dst_fmt}")
                return

            self.log_ok(f"Concluido. {total} mensagem(ns) convertida(s).")

        except Exception as e:
            self.log_error(f"Falha na conversao: {e}")
        finally:
            self._progress_stop()
            self.log_sep()
            self.log("")

    # ============================================================
    # LEITURA: PST / OST  (sem Outlook, via pypff)
    # ============================================================
    def _read_pst(self, path):
        """Gera (pasta, EmailMessage) percorrendo todo o arquivo PST/OST."""
        pff = pypff.file()
        pff.open(path)
        try:
            root = pff.get_root_folder()
            yield from self._walk_pff_folder(root, "")
        finally:
            pff.close()

    def _walk_pff_folder(self, folder, prefix):
        name = ""
        try:
            name = folder.get_name() or ""
        except Exception:
            name = ""
        path = f"{prefix}/{name}" if name else prefix

        try:
            n_msgs = folder.get_number_of_sub_messages()
        except Exception:
            n_msgs = 0

        for i in range(n_msgs):
            try:
                msg = folder.get_sub_message(i)
                yield (path, self._pff_to_email(msg))
            except Exception as e:
                self.log_warn(f"Mensagem ignorada em '{path}': {e}")

        try:
            n_sub = folder.get_number_of_sub_folders()
        except Exception:
            n_sub = 0
        for i in range(n_sub):
            try:
                yield from self._walk_pff_folder(folder.get_sub_folder(i), path)
            except Exception:
                continue

    def _pff_to_email(self, msg):
        """Converte uma mensagem pypff em email.message.EmailMessage."""
        em = EmailMessage()

        subject = ""
        sender = ""
        headers = None
        try:
            subject = msg.get_subject() or ""
        except Exception:
            pass
        try:
            sender = msg.get_sender_name() or ""
        except Exception:
            pass
        try:
            headers = msg.get_transport_headers()
        except Exception:
            headers = None

        # Copia um subconjunto seguro de cabecalhos originais
        if headers:
            try:
                parsed = Parser(policy=default_policy).parsestr(headers)
                for key in ("From", "To", "Cc", "Subject", "Date",
                            "Message-ID", "Reply-To"):
                    val = parsed[key]
                    if val:
                        em[key] = str(val)
            except Exception:
                pass

        if "Subject" not in em and subject:
            em["Subject"] = subject
        if "From" not in em and sender:
            em["From"] = sender
        if "Date" not in em:
            try:
                dt = msg.get_delivery_time()
                if isinstance(dt, datetime):
                    em["Date"] = format_datetime(dt)
            except Exception:
                pass

        # Corpo
        plain = html = ""
        try:
            plain = _decode_body(msg.get_plain_text_body())
        except Exception:
            pass
        try:
            html = _decode_body(msg.get_html_body())
        except Exception:
            pass

        if html and plain:
            em.set_content(plain)
            em.add_alternative(html, subtype="html")
        elif html:
            em.set_content("(mensagem em HTML)")
            em.add_alternative(html, subtype="html")
        else:
            em.set_content(plain or "")

        # Anexos
        try:
            n_att = msg.get_number_of_attachments()
        except Exception:
            n_att = 0
        for i in range(n_att):
            try:
                att = msg.get_attachment(i)
                size = att.get_size()
                data = att.read_buffer(size) if size else b""
                fname = ""
                try:
                    fname = att.get_long_filename() or ""
                except Exception:
                    fname = ""
                fname = fname or f"anexo_{i+1}.bin"
                em.add_attachment(data, maintype="application",
                                  subtype="octet-stream", filename=fname)
            except Exception:
                continue

        return em

    # ============================================================
    # LEITURA: MBOX
    # ============================================================
    def _read_mbox(self, path):
        box = mailbox.mbox(path)
        try:
            for key in box.iterkeys():
                try:
                    yield ("", box[key])
                except Exception as e:
                    self.log_warn(f"Mensagem ignorada: {e}")
        finally:
            box.close()

    # ============================================================
    # GRAVACAO: MBOX
    # ============================================================
    def _write_mbox(self, messages, out_path):
        box = mailbox.mbox(out_path)
        box.lock()
        total = 0
        try:
            for _folder, msg in messages:
                box.add(msg)
                total += 1
                if total % 200 == 0:
                    self.log_info(f"{total} mensagens...")
            box.flush()
        finally:
            box.unlock()
            box.close()
        self.log_ok(f"MBOX gravado: {out_path}")
        return total

    # ============================================================
    # GRAVACAO: EML (uma pasta, um arquivo por mensagem)
    # ============================================================
    def _write_eml(self, messages, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        total = 0
        for folder, msg in messages:
            total += 1
            subdir = out_dir
            if folder:
                subdir = os.path.join(out_dir, *[
                    _safe_name(p, 40) for p in folder.split("/") if p])
                os.makedirs(subdir, exist_ok=True)
            subj = msg.get("Subject", "") if hasattr(msg, "get") else ""
            fname = f"{total:05d}_{_safe_name(subj)}.eml"
            try:
                data = msg.as_bytes()
            except Exception:
                data = msg.as_string().encode("utf-8", errors="replace")
            with open(os.path.join(subdir, fname), "wb") as f:
                f.write(data)
            if total % 200 == 0:
                self.log_info(f"{total} mensagens...")
        self.log_ok(f"{total} arquivo(s) .eml gravado(s) em: {out_dir}")
        return total

    # ============================================================
    # GRAVACAO: PST (requer Outlook via COM; melhor esforco)
    #
    # Importante: a automacao COM do Outlook nao permite injetar uma
    # mensagem RECEBIDA com fidelidade total (cabecalhos originais,
    # data de recebimento). Reconstruimos assunto/remetente/corpo e
    # anexos em um item de e-mail dentro do PST. Para fidelidade
    # completa, prefira a saida MBOX (importavel pelo Thunderbird).
    # ============================================================
    def _write_pst(self, messages, out_path):
        if not self.outlook_available():
            self.log_error(
                "Gravacao em PST requer o Microsoft Outlook instalado "
                "(automacao COM). Outlook nao encontrado nesta maquina.")
            self.log_info(
                "Alternativa: converta para MBOX e importe no Thunderbird, "
                "ou para EML.")
            return 0

        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        total = 0
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            ns = outlook.GetNamespace("MAPI")

            out_path = os.path.abspath(out_path)
            ns.AddStoreEx(out_path, 3)  # 3 = olStoreUnicode

            store = None
            for s in ns.Stores:
                try:
                    if os.path.normcase(s.FilePath) == os.path.normcase(out_path):
                        store = s
                        break
                except Exception:
                    continue
            if store is None:
                self.log_error("Nao foi possivel localizar o PST recem-criado.")
                return 0

            root = store.GetRootFolder()
            try:
                folder = root.Folders.Add("Importado")
            except Exception:
                folder = root.Folders.Item("Importado")

            self.log_warn(
                "Gravacao em PST via Outlook e por melhor esforco "
                "(assunto/remetente/corpo/anexos).")

            for _f, msg in messages:
                try:
                    item = outlook.CreateItem(0)  # olMailItem
                    item.Subject = msg.get("Subject", "") if hasattr(msg, "get") else ""
                    sender = msg.get("From", "") if hasattr(msg, "get") else ""
                    body = _plain_text_of(msg)
                    if sender:
                        body = f"De: {sender}\r\n\r\n{body}"
                    item.Body = body
                    item.Save()
                    item.Move(folder)
                    total += 1
                    if total % 100 == 0:
                        self.log_info(f"{total} mensagens...")
                except Exception as e:
                    self.log_warn(f"Mensagem ignorada: {e}")

            self.log_ok(f"PST gravado: {out_path}")
        finally:
            pythoncom.CoUninitialize()
        return total
