"""
Gera relatorios HTML autocontidos (sidebar + conteudo, estilo AIDA64) a
partir dos dicionarios produzidos por util.schemes.SchemeBuilder.collect().

Duas entradas publicas:
    render_report(data)                -> relatorio de uma unica maquina
    render_consolidated(entries)       -> relatorio consolidado de varias
                                           maquinas (entries = [(label, data), ...])

Nao depende de util.schemes (evita import circular) e e tolerante a
schemas com chaves ausentes/adicionais, entao funciona com qualquer
versao do schema_version.
"""

import html as _html
from string import Template

# Paleta identica a usada em gui.py, para o relatorio manter a
# identidade visual do aplicativo.
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

# Segunda cor categorica (identidade), usada apenas quando duas series
# distintas de fato precisam ser diferenciadas (ex.: TCP vs UDP). Nao e
# reutilizada como status - mantem-se fora do trio verde/laranja/vermelho
# acima para nao ser confundida com um sinal de severidade.
C_CAT2 = "#9085e9"

# Paleta categorica para pizzas com N series (ex.: fabricantes, tipos de
# memoria) - nunca inclui as cores de severidade (verde/laranja/vermelho),
# que ficam reservadas a graficos de uso/status.
C_CATEGORICAL = [
    C_ACCENT, C_CAT2, "#2fb8c6", "#e2739d",
    "#d4b23c", "#6f7bd6", "#8891b0", "#3f9fe0",
]

SECTION_TITLES = {
    "system":             "Sistema",
    "bios":               "BIOS",
    "motherboard":        "Placa Mae",
    "cpu":                "CPU",
    "memory":             "Memoria RAM",
    "storage":             "Armazenamento",
    "disk_health":         "Saude dos Discos",
    "gpu":                "GPU",
    "network":            "Rede",
    "open_ports":         "Portas Abertas",
    "audio":              "Audio",
    "software":           "Software",
    "installed_programs": "Programas Instalados",
    "startup_programs":   "Inicializacao",
    "local_users":        "Usuarios Locais",
    "antivirus":          "Antivirus",
    "email_clients":      "Clientes de Email",
    "event_log":          "Eventos do Sistema",
    "runtime":            "Runtime",
}

SKIP_KEYS = {"schema_version", "generated_at"}


# ============================================================
# HELPERS DE ESCAPE / FORMATACAO
# ============================================================
def _esc(value):
    if value is None:
        return ""
    return _html.escape(str(value))


def _title(key):
    return SECTION_TITLES.get(key, str(key).replace("_", " ").title())


def _safe(d, *path, default="N/A"):
    cur = d
    for p in path:
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, list):
            try:
                cur = cur[p]
            except (IndexError, TypeError):
                return default
        else:
            return default
        if cur is None:
            return default
    return cur if cur != "" else default


def _render_scalar(v):
    if isinstance(v, bool):
        cls = "yes" if v else "no"
        return f"<span class='pill {cls}'>{'Sim' if v else 'Nao'}</span>"
    if isinstance(v, list):
        if not v:
            return "<span class='dim'>-</span>"
        return "".join(f"<span class='tag'>{_esc(i)}</span>" for i in v)
    if isinstance(v, dict):
        return _esc(v)
    if v is None or v == "":
        return "<span class='dim'>N/A</span>"
    return _esc(v)


def _status_color(pct):
    """Verde/laranja/vermelho por limiar - escala de severidade fixa,
    reservada e nunca reaproveitada como identidade de serie."""
    try:
        pct_f = float(pct)
    except (TypeError, ValueError):
        return C_ACCENT
    if pct_f < 70:
        return C_SUCCESS
    if pct_f < 90:
        return C_WARNING
    return C_DANGER


def _progress_bar(pct, label="uso"):
    try:
        pct_f = float(pct)
    except (TypeError, ValueError):
        pct_f = 0.0
    pct_f = max(0.0, min(100.0, pct_f))
    color = _status_color(pct_f)
    return (
        f"<div class='progress'><div class='progress-bar' "
        f"style='width:{pct_f}%;background:{color}'></div></div>"
        f"<small>{_esc(pct)}% {_esc(label)}</small>"
    )


# ============================================================
# GRAFICOS DE BARRA (HTML/CSS, sem dependencias externas)
# ============================================================
def _bar_chart(title, rows, unit="", legend=None, max_value=None, note=None):
    """
    rows: lista de tuplas (label, valor, cor).
    legend: lista opcional de (label, cor) - exibida quando ha 2+ series
            (identidade por cor); omitida para grafico de serie unica.
    """
    if not rows:
        return ""

    numeric = []
    for label, value, color in rows:
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            numeric.append(0.0)

    max_v = max_value if max_value is not None else (max(numeric) or 1)

    legend_html = ""
    if legend:
        items = "".join(
            f"<span class='legend-item'>"
            f"<span class='legend-swatch' style='background:{c}'></span>{_esc(l)}"
            f"</span>"
            for l, c in legend
        )
        legend_html = f"<div class='chart-legend'>{items}</div>"

    bars = ""
    for (label, value, color), value_f in zip(rows, numeric):
        width_pct = 1.5 if max_v <= 0 else max(1.5, min(100.0, (value_f / max_v) * 100))
        value_label = f"{_esc(value)}{_esc(unit)}"
        bars += (
            "<div class='bar-row'>"
            f"<div class='bar-label' title='{_esc(label)}'>{_esc(label)}</div>"
            f"<div class='bar-track' title='{_esc(label)}: {value_label}'>"
            f"<div class='bar-fill' style='width:{width_pct}%;background:{color}'></div>"
            "</div>"
            f"<div class='bar-value'>{value_label}</div>"
            "</div>"
        )

    note_html = f"<p class='chart-note'>{_esc(note)}</p>" if note else ""

    return (
        "<div class='chart'>"
        f"<div class='chart-title'>{_esc(title)}</div>"
        f"{legend_html}"
        f"<div class='chart-body'>{bars}</div>"
        f"{note_html}"
        "</div>"
    )


# ============================================================
# GRAFICOS DE PIZZA (donut via CSS conic-gradient, sem dependencias)
# ============================================================
def _pie_chart(title, slices, unit="", note=None, center_label=None):
    """
    slices: lista de tuplas (label, valor, cor).
    center_label: texto exibido no centro do donut (ex.: total). Se
    omitido, usa a soma dos valores.
    """
    numeric = []
    for label, value, color in slices:
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = 0.0
        numeric.append(max(0.0, v))

    total = sum(numeric)
    if total <= 0:
        return ""

    stops = []
    cursor = 0.0
    for (label, value, color), value_f in zip(slices, numeric):
        start = (cursor / total) * 100
        cursor += value_f
        end = (cursor / total) * 100
        stops.append(f"{color} {start:.2f}% {end:.2f}%")

    gradient = ", ".join(stops)

    legend_items = ""
    for (label, value, color), value_f in zip(slices, numeric):
        pct = (value_f / total) * 100
        legend_items += (
            "<div class='pie-legend-item'>"
            f"<span class='legend-swatch' style='background:{color}'></span>"
            f"<span class='pie-legend-label'>{_esc(label)}</span>"
            f"<span class='pie-legend-value'>{_esc(value)}{_esc(unit)} "
            f"<small>({pct:.1f}%)</small></span>"
            "</div>"
        )

    center = _esc(center_label) if center_label is not None else _esc(round(total, 2))
    note_html = f"<p class='chart-note'>{_esc(note)}</p>" if note else ""

    return (
        "<div class='pie-chart'>"
        f"<div class='chart-title'>{_esc(title)}</div>"
        "<div class='pie-body'>"
        f"<div class='pie' style='background:conic-gradient({gradient})'>"
        f"<div class='pie-hole'><span>{center}</span></div>"
        "</div>"
        f"<div class='pie-legend'>{legend_items}</div>"
        "</div>"
        f"{note_html}"
        "</div>"
    )


def _top_n_with_others(counts, n=6, others_label="Outros", others_color=C_DIM):
    """Recebe {label: valor} e devolve as N maiores fatias + uma fatia
    'Outros' agregando o restante, coloridas pela paleta categorica."""
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top     = ordered[:n]
    rest    = ordered[n:]
    slices  = [
        (label, value, C_CATEGORICAL[i % len(C_CATEGORICAL)])
        for i, (label, value) in enumerate(top)
    ]
    if rest:
        slices.append((others_label, sum(v for _, v in rest), others_color))
    return slices


def _render_storage_charts(storage):
    if not isinstance(storage, dict):
        return ""
    volumes = storage.get("volumes") or []
    drives  = storage.get("drives") or []
    html    = ""

    if volumes:
        total_used = sum(float(v.get("used_gb") or 0) for v in volumes)
        total_free = sum(float(v.get("free_gb") or 0) for v in volumes)
        total_gb   = total_used + total_free
        if total_gb > 0:
            used_pct = (total_used / total_gb) * 100
            html += _pie_chart(
                "Uso Total de Armazenamento",
                [
                    ("Usado", round(total_used, 2), _status_color(used_pct)),
                    ("Livre", round(total_free, 2), C_BORDER),
                ],
                unit=" GB",
                center_label=f"{used_pct:.0f}%",
                note="Soma de todos os volumes montados.",
            )

        rows = [
            (v.get("mount_point", "?"), v.get("usage_pct", 0), _status_color(v.get("usage_pct")))
            for v in volumes
        ]
        html += _bar_chart(
            "Uso por Volume", rows, unit="%", max_value=100,
            note="Verde < 70% · Laranja < 90% · Vermelho ≥ 90%",
        )

    if drives:
        rows = [
            (d.get("model", "?"), d.get("size_gb", 0), C_ACCENT)
            for d in drives
        ]
        html += _bar_chart("Capacidade dos Discos", rows, unit=" GB")

    return html


def _render_memory_charts(memory):
    if not isinstance(memory, dict):
        return ""
    html = ""

    total_gb = memory.get("total_gb")
    used_gb  = memory.get("used_gb")
    avail_gb = memory.get("available_gb")
    if total_gb and used_gb is not None and avail_gb is not None:
        used_pct = memory.get("usage_pct") or (used_gb / total_gb * 100 if total_gb else 0)
        html += _pie_chart(
            "Composicao da Memoria",
            [
                ("Em uso",    used_gb,  _status_color(used_pct)),
                ("Disponivel", avail_gb, C_BORDER),
            ],
            unit=" GB",
            center_label=f"{used_pct:.0f}%",
        )

    modules = memory.get("modules") or []
    if len(modules) > 1:
        type_counts = {}
        for m in modules:
            t = m.get("type") or "Desconhecido"
            type_counts[t] = type_counts.get(t, 0) + 1
        if len(type_counts) > 1:
            slices = [
                (t, count, C_CATEGORICAL[i % len(C_CATEGORICAL)])
                for i, (t, count) in enumerate(type_counts.items())
            ]
            html += _pie_chart(
                "Modulos por Tipo", slices, unit=" modulo(s)",
                center_label=str(len(modules)),
            )

    return html


_DISK_HEALTH_PILL = {"Saudavel": "yes", "Aviso": "warn", "Nao Saudavel": "no"}


def _render_disk_health_chart(disks):
    wear_rows = [
        (d.get("model", "?"), d.get("wear_pct"), _status_color(d.get("wear_pct")))
        for d in disks
        if isinstance(d, dict) and d.get("wear_pct") is not None
    ]
    if not wear_rows:
        return ""
    return _bar_chart(
        "Desgaste dos Discos (SSD)", wear_rows, unit="%", max_value=100,
        note="Percentual estimado de vida util consumida (SMART/Storage Reliability).",
    )


def _render_disk_health(disks):
    if not disks:
        return "<p class='empty'>Nenhum disco fisico detectado.</p>"

    cards = ""
    for d in disks:
        if not isinstance(d, dict):
            continue
        status   = d.get("health_status", "Desconhecido")
        pill_cls = _DISK_HEALTH_PILL.get(status, "no")
        wear     = d.get("wear_pct")
        poh      = d.get("power_on_hours")
        poh_days = d.get("power_on_days")
        temp     = d.get("temperature_c")
        note     = d.get("reliability_unavailable")

        cards += "<div class='card'>"
        cards += f"<h3>{_esc(d.get('model', 'Disco'))}</h3>"
        cards += f"<p><b>Status:</b> <span class='pill {pill_cls}'>{_esc(status)}</span></p>"
        cards += f"<p><b>Tipo:</b> {_esc(d.get('media_type', 'N/A'))} &middot; {_esc(d.get('bus_type', 'N/A'))}</p>"
        cards += f"<p><b>Capacidade:</b> {_esc(d.get('size_gb', 'N/A'))} GB</p>"
        if wear is not None:
            cards += f"<p><b>Desgaste (vida usada):</b> {_esc(wear)}%</p>"
            cards += _progress_bar(wear, label="desgaste")
        if poh is not None:
            dias = f" (&asymp;{_esc(poh_days)} dias)" if poh_days is not None else ""
            cards += f"<p><b>Horas ligado:</b> {_esc(poh)}h{dias}</p>"
        if temp is not None:
            cards += f"<p><b>Temperatura:</b> {_esc(temp)}&deg;C</p>"
        if note:
            cards += f"<p class='dim'>{_esc(note)}</p>"
        cards += "</div>"

    return _render_disk_health_chart(disks) + f"<div class='grid'>{cards}</div>"


def _render_ports_charts(ports):
    if not ports:
        return ""

    tcp_count = sum(1 for p in ports if str(p.get("protocol", "")).upper() == "TCP")
    udp_count = sum(1 for p in ports if str(p.get("protocol", "")).upper() == "UDP")

    html = _pie_chart(
        "Portas por Protocolo",
        [("TCP", tcp_count, C_ACCENT), ("UDP", udp_count, C_CAT2)],
        unit=" porta(s)",
        center_label=str(tcp_count + udp_count),
    )

    counts = {}
    for p in ports:
        name = p.get("process") or "N/A"
        counts[name] = counts.get(name, 0) + 1
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
    if top:
        rows = [(name, count, C_ACCENT) for name, count in top]
        html += _bar_chart("Processos com Mais Portas Abertas", rows)

    return html


def _render_installed_programs_charts(programs):
    if not programs:
        return ""
    counts = {}
    for p in programs:
        vendor = (p.get("vendor") or "Desconhecido").strip() or "Desconhecido"
        counts[vendor] = counts.get(vendor, 0) + 1
    if len(counts) < 2:
        return ""
    slices = _top_n_with_others(counts, n=7)
    return _pie_chart(
        "Programas por Fabricante", slices, unit=" programa(s)",
        center_label=str(len(programs)),
    )


def _render_event_log_charts(logs):
    if not isinstance(logs, dict) or not logs:
        return ""
    html = ""
    for log_name, info in logs.items():
        if not isinstance(info, dict) or info.get("error"):
            continue
        by_source = info.get("by_source") or {}
        if not by_source:
            continue
        html += _bar_chart(
            f"Fontes Mais Frequentes — {log_name}",
            _top_n_with_others(by_source, n=8),
        )
    return html


def _render_event_log(logs):
    if not isinstance(logs, dict) or not logs:
        return "<p class='empty'>Nenhum log de eventos coletado.</p>"

    html = ""
    for log_name, info in logs.items():
        if not isinstance(info, dict):
            continue

        html += f"<h3>{_esc(log_name)}</h3>"

        if info.get("error"):
            html += (
                f"<p class='empty'>Nao foi possivel ler este log: "
                f"{_esc(info['error'])}</p>"
            )
            continue

        total  = info.get("total_matched", 0)
        shown  = info.get("shown", 0)
        window = info.get("window_days", "?")
        cap_note = (
            f" (exibindo os {shown} mais recentes)" if shown < total else ""
        )
        html += (
            f"<p class='meta-sub'>{total} evento(s) relevante(s) nos "
            f"ultimos {window} dia(s){cap_note}.</p>"
        )

        by_source = info.get("by_source") or {}
        if by_source:
            html += _bar_chart(
                f"Fontes Mais Frequentes — {log_name}",
                _top_n_with_others(by_source, n=8),
            )

        entries = info.get("entries") or []
        if entries:
            rows = [
                {
                    "Data/Hora": e.get("time", "N/A"),
                    "Nivel":     e.get("level", "N/A"),
                    "Origem":    e.get("source", "N/A"),
                    "ID":        e.get("event_id", "N/A"),
                    "Mensagem":  e.get("message", ""),
                }
                for e in entries
            ]
            html += _list_table(rows)
        else:
            html += "<p class='empty'>Nenhum evento relevante no periodo.</p>"

    return html


def _render_local_users_charts(users):
    if not users:
        return ""
    enabled  = sum(1 for u in users if not u.get("disabled"))
    disabled = sum(1 for u in users if u.get("disabled"))
    locked   = sum(1 for u in users if u.get("locked_out"))

    slices = [("Ativos", enabled, C_SUCCESS)]
    if disabled:
        slices.append(("Desativados", disabled, C_DIM))
    if locked:
        slices.append(("Bloqueados", locked, C_DANGER))
    if len(slices) < 2:
        return ""
    return _pie_chart(
        "Usuarios por Status", slices, unit=" usuario(s)",
        center_label=str(len(users)),
    )


def _render_email_clients(clients):
    if not clients:
        return "<p class='empty'>Nenhum cliente de email detectado.</p>"

    html = ""
    for c in clients:
        if not isinstance(c, dict):
            continue
        name     = c.get("client", "Desconhecido")
        accounts = c.get("accounts") or []
        html += (
            f"<h3>{_esc(name)} "
            f"<span class='tag'>{len(accounts)} conta(s)</span></h3>"
        )
        if accounts:
            rows = [
                {
                    "Conta":  a.get("display_name", "N/A"),
                    "Email":  a.get("email", "N/A"),
                    "Perfil": a.get("profile", "N/A"),
                }
                for a in accounts
            ]
            html += _list_table(rows)
        else:
            html += (
                "<p class='empty'>Cliente detectado, mas nenhuma conta "
                "configurada foi encontrada.</p>"
            )
    return html


def _render_section(key, value):
    """Despacha secoes que ganham um tratamento dedicado (graficos,
    tabelas customizadas); as demais caem no renderizador generico."""
    if key == "email_clients" and isinstance(value, list):
        return _render_email_clients(value)
    if key == "storage" and isinstance(value, dict):
        return _render_storage_charts(value) + _render_section_body(value)
    if key == "disk_health" and isinstance(value, list):
        return _render_disk_health(value)
    if key == "open_ports" and isinstance(value, list):
        return _render_ports_charts(value) + _render_section_body(value)
    if key == "memory" and isinstance(value, dict):
        return _render_memory_charts(value) + _render_section_body(value)
    if key == "installed_programs" and isinstance(value, list):
        return _render_installed_programs_charts(value) + _render_section_body(value)
    if key == "local_users" and isinstance(value, list):
        return _render_local_users_charts(value) + _render_section_body(value)
    if key == "event_log" and isinstance(value, dict):
        return _render_event_log(value)
    return _render_section_body(value)


# ============================================================
# TABELAS
# ============================================================
def _kv_table(pairs):
    if not pairs:
        return "<p class='empty'>Sem dados.</p>"
    rows = "".join(
        f"<tr><th>{_esc(_title(k))}</th><td>{_render_scalar(v)}</td></tr>"
        for k, v in pairs
    )
    return f"<table class='kv'>{rows}</table>"


def _list_table(rows):
    if not rows:
        return "<p class='empty'>Sem dados.</p>"

    if not any(isinstance(r, dict) for r in rows):
        items = "".join(f"<span class='tag'>{_esc(i)}</span>" for i in rows)
        return f"<div class='tags'>{items}</div>"

    headers = []
    for row in rows:
        if isinstance(row, dict):
            for k in row.keys():
                if k not in headers:
                    headers.append(k)

    thead = "".join(f"<th>{_esc(_title(h))}</th>" for h in headers)
    body = ""
    for row in rows:
        if not isinstance(row, dict):
            continue
        cells = "".join(f"<td>{_render_scalar(row.get(h, ''))}</td>" for h in headers)
        body += f"<tr>{cells}</tr>"

    return (
        f"<div class='table-wrap'><table class='list'>"
        f"<thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _render_section_body(value):
    if isinstance(value, list):
        return _list_table(value)

    if isinstance(value, dict):
        scalar_pairs = [
            (k, v) for k, v in value.items() if not isinstance(v, (list, dict))
        ]
        list_pairs = [(k, v) for k, v in value.items() if isinstance(v, list)]
        dict_pairs = [(k, v) for k, v in value.items() if isinstance(v, dict)]

        out = _kv_table(scalar_pairs) if scalar_pairs else ""
        for k, v in dict_pairs:
            out += f"<h3>{_esc(_title(k))}</h3>{_render_section_body(v)}"
        for k, v in list_pairs:
            if v:
                out += f"<h3>{_esc(_title(k))}</h3>{_list_table(v)}"
        return out or "<p class='empty'>Sem dados.</p>"

    return _kv_table([("valor", value)])


def _dashboard_section(title, key, chart_html, target_prefix=""):
    """Bloco clicavel do Dashboard: titulo funciona como nav-link (reaproveita
    o mesmo mecanismo de navegacao da sidebar) para pular direto a secao
    completa. Omitido quando a secao nao tem grafico (nada para mostrar)."""
    if not chart_html:
        return ""
    return (
        "<div class='dash-section'>"
        f"<a class='dash-section-title nav-link' data-target='{target_prefix}{key}' href='#'>"
        f"{_esc(title)} <span class='dash-arrow'>&rarr;</span></a>"
        f"<div class='dash-section-body'>{chart_html}</div>"
        "</div>"
    )


def _dashboard_html(data, target_prefix=""):
    sysd = data.get("system", {}) or {}
    cpud = data.get("cpu", {}) or {}
    memd = data.get("memory", {}) or {}
    stor = data.get("storage", {}) or {}
    runtime = data.get("runtime", {}) or {}

    volumes = stor.get("volumes") or []
    vol0    = volumes[0] if volumes else {}
    drives  = stor.get("drives") or []
    drive0  = drives[0] if drives else {}
    health  = data.get("disk_health") or []
    health0 = health[0] if health else {}

    cpu_pct  = runtime.get("cpu_usage_pct", 0)
    ram_pct  = memd.get("usage_pct", 0)
    disk_pct = vol0.get("usage_pct", 0)

    kpi_html = f"""
    <div class="grid">
        <div class="card">
            <h3>Sistema</h3>
            <p><b>SO:</b> {_esc(sysd.get('os_edition') or sysd.get('os', 'N/A'))}</p>
            <p><b>Build:</b> {_esc(sysd.get('os_build', 'N/A'))}</p>
            <p><b>Boot:</b> {_esc(sysd.get('boot_mode', 'N/A'))}</p>
            <p><b>Uptime:</b> {_esc(sysd.get('uptime', 'N/A'))}</p>
        </div>
        <div class="card">
            <h3>CPU</h3>
            <p>{_esc(cpud.get('model') or cpud.get('processor', 'N/A'))}</p>
            {_progress_bar(cpu_pct)}
        </div>
        <div class="card">
            <h3>RAM</h3>
            <p>{_esc(memd.get('total_gb', 'N/A'))} GB</p>
            {_progress_bar(ram_pct)}
        </div>
        <div class="card">
            <h3>Disco</h3>
            <p>{_esc(drive0.get('model', 'N/A'))}</p>
            {_progress_bar(disk_pct)}
            {(
                f"<p><b>Saude:</b> <span class='pill {_DISK_HEALTH_PILL.get(health0.get('health_status'), 'no')}'>"
                f"{_esc(health0.get('health_status'))}</span></p>"
            ) if health0 else ""}
        </div>
    </div>
    """

    # Galeria: cada secao que produz grafico entra aqui, resumida ("rasa"),
    # com o titulo levando direto ao painel completo daquela secao.
    sections_html = ""
    sections_html += _dashboard_section("Memoria",              "memory",              _render_memory_charts(memd),                       target_prefix)
    sections_html += _dashboard_section("Armazenamento",        "storage",             _render_storage_charts(stor),                      target_prefix)
    sections_html += _dashboard_section("Saude dos Discos",     "disk_health",         _render_disk_health_chart(data.get("disk_health") or []), target_prefix)
    sections_html += _dashboard_section("Portas Abertas",       "open_ports",          _render_ports_charts(data.get("open_ports") or []), target_prefix)
    sections_html += _dashboard_section("Programas Instalados", "installed_programs",  _render_installed_programs_charts(data.get("installed_programs") or []), target_prefix)
    sections_html += _dashboard_section("Usuarios Locais",      "local_users",         _render_local_users_charts(data.get("local_users") or []), target_prefix)
    sections_html += _dashboard_section("Eventos do Sistema",   "event_log",           _render_event_log_charts(data.get("event_log") or {}), target_prefix)

    return kpi_html + f"<div class='dash-grid'>{sections_html}</div>"


# ============================================================
# CSS / JS ESTATICOS
# ============================================================
_CSS_TEMPLATE = Template("""
:root {
  --bg:$BG; --panel:$PANEL; --card:$CARD; --card2:$CARD2;
  --hover:$HOVER; --border:$BORDER; --accent:$ACCENT; --accent2:$ACCENT2;
  --text:$TEXT; --dim:$DIM; --success:$SUCCESS; --warning:$WARNING; --danger:$DANGER;
}
* { box-sizing:border-box; margin:0; padding:0; }
html, body { height:100%; }
body {
  font-family:'Segoe UI',Arial,sans-serif; background:var(--bg); color:var(--text);
  font-size:14px; display:flex; flex-direction:column; height:100vh; overflow:hidden;
}
.topbar {
  background:var(--panel); border-bottom:1px solid var(--border);
  padding:12px 20px; display:flex; align-items:center; justify-content:space-between;
  flex-wrap:wrap; gap:10px; flex-shrink:0;
}
.brand { font-size:18px; font-weight:700; color:var(--accent); }
.meta-line { font-size:12px; color:var(--dim); margin-top:2px; }
.search-box input {
  width:240px; padding:7px 10px; background:var(--card); border:1px solid var(--border);
  color:var(--text); border-radius:4px; font-size:12px;
}
.search-box input:focus { outline:1px solid var(--accent); }
.body-wrap { flex:1; display:flex; min-height:0; }
.sidebar {
  width:280px; flex-shrink:0; background:var(--panel); border-right:1px solid var(--border);
  overflow-y:auto; padding:10px 0;
}
.nav, .nav-sub { list-style:none; }
.nav-link, .nav-group-header {
  display:block; padding:8px 18px; color:var(--dim); text-decoration:none;
  font-size:13px; cursor:pointer; border-left:2px solid transparent;
}
.nav-link:hover, .nav-group-header:hover { background:var(--hover); color:var(--text); }
.nav-link.active { background:var(--card2); color:var(--accent); border-left-color:var(--accent); font-weight:600; }
.nav-group-header { font-weight:600; color:var(--text); display:flex; align-items:center; gap:7px; }
.nav-group-header .arrow { font-size:10px; color:var(--dim); transition:transform .15s; }
.nav-group:not(.collapsed) .nav-group-header .arrow { transform:rotate(90deg); }
.nav-group.collapsed .nav-sub { display:none; }
.nav-sub .nav-link { padding-left:34px; font-size:12.5px; }
.content { flex:1; overflow-y:auto; padding:24px 32px 60px; }
.panel { display:none; }
.panel.active { display:block; }
.panel h2 {
  color:var(--accent); font-size:16px; text-transform:uppercase; letter-spacing:.06em;
  border-bottom:1px solid var(--border); padding-bottom:8px; margin-bottom:16px;
}
.panel h3 {
  font-size:12px; margin:18px 0 8px; color:var(--dim);
  text-transform:uppercase; letter-spacing:.05em;
}
.meta-sub { color:var(--dim); font-size:12px; margin-bottom:14px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin-bottom:10px; }
.card { background:var(--card2); border:1px solid var(--border); border-radius:6px; padding:14px 16px; }
.card h3 { margin:0 0 8px; color:var(--accent); font-size:13px; text-transform:none; letter-spacing:0; }
.card p { font-size:13px; margin:2px 0; color:var(--text); }
table { border-collapse:collapse; width:100%; }
table.kv th { width:240px; }
th {
  background:var(--card2); color:var(--accent); text-align:left; padding:8px 12px;
  border-bottom:1px solid var(--border); font-size:12.5px; font-weight:600;
}
td { padding:7px 12px; border-bottom:1px solid var(--border); font-size:12.5px; }
tr:hover td { background:var(--hover); }
.table-wrap { overflow:auto; max-height:65vh; border:1px solid var(--border); border-radius:6px; margin-bottom:14px; }
.table-wrap table { margin:0; }
.table-wrap th { position:sticky; top:0; }
.dash-table tbody tr { cursor:pointer; }
.empty { color:var(--dim); font-size:13px; padding:8px 0; }
.progress { width:100%; height:14px; background:var(--card); border:1px solid var(--border); border-radius:3px; margin-top:6px; overflow:hidden; }
.progress-bar { height:100%; }
small { color:var(--dim); font-size:11px; }
.tag {
  display:inline-block; background:var(--card); border:1px solid var(--border);
  padding:2px 8px; margin:2px 3px 2px 0; font-size:11px; border-radius:10px; color:var(--text);
}
.pill { padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; }
.pill.yes { background:rgba(72,216,144,.15); color:var(--success); }
.pill.no { background:rgba(232,80,80,.15); color:var(--danger); }
.pill.warn { background:rgba(240,160,64,.15); color:var(--warning); }
.dim { color:var(--dim); }
.chart { margin:10px 0 20px; }
.chart-title {
  font-size:12px; font-weight:600; color:var(--text); text-transform:uppercase;
  letter-spacing:.04em; margin-bottom:10px;
}
.chart-legend { display:flex; gap:16px; margin-bottom:8px; flex-wrap:wrap; }
.legend-item { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--dim); }
.legend-swatch { width:10px; height:10px; border-radius:2px; display:inline-block; flex-shrink:0; }
.chart-body { display:flex; flex-direction:column; gap:6px; }
.bar-row { display:flex; align-items:center; gap:10px; }
.bar-label {
  width:190px; flex-shrink:0; font-size:12px; color:var(--dim);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.bar-track { flex:1; height:14px; background:var(--card); border-radius:0 4px 4px 0; overflow:hidden; }
.bar-fill { height:100%; min-width:2px; border-radius:0 4px 4px 0; }
.bar-value {
  width:76px; flex-shrink:0; text-align:right; font-size:12px; color:var(--text);
  font-variant-numeric:tabular-nums;
}
.chart-note { font-size:11px; color:var(--dim); margin-top:8px; }
.pie-chart { margin:10px 0 20px; }
.pie-body { display:flex; align-items:center; gap:24px; flex-wrap:wrap; }
.pie {
  width:130px; height:130px; border-radius:50%; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
}
.pie-hole {
  width:76px; height:76px; border-radius:50%; background:var(--card2);
  border:1px solid var(--border); display:flex; align-items:center; justify-content:center;
}
.pie-hole span { font-size:14px; font-weight:700; color:var(--text); }
.pie-legend { display:flex; flex-direction:column; gap:6px; }
.pie-legend-item { display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--text); }
.pie-legend-label { color:var(--dim); min-width:110px; }
.pie-legend-value { font-variant-numeric:tabular-nums; }
.pie-legend-value small { color:var(--dim); }
.dash-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:16px; margin-top:18px; }
.dash-section {
  background:var(--card2); border:1px solid var(--border); border-radius:6px;
  padding:14px 16px; min-width:0;
}
.dash-section-title {
  display:flex; align-items:center; justify-content:space-between; gap:8px;
  font-size:13px; font-weight:600; color:var(--accent); text-decoration:none;
  padding-bottom:8px; margin-bottom:8px; border-bottom:1px solid var(--border);
}
.dash-section-title:hover { color:var(--text); }
.dash-arrow { color:var(--dim); font-weight:400; }
.dash-section-body .chart,
.dash-section-body .pie-chart { margin:6px 0 14px; }
.dash-section-body .chart-title { font-size:11px; margin-bottom:6px; }
.dash-section-body .pie { width:90px; height:90px; }
.dash-section-body .pie-hole { width:54px; height:54px; }
.dash-section-body .pie-hole span { font-size:11px; }
.dash-section-body .pie-legend-label { min-width:70px; }
.dash-section-body .bar-label { width:120px; }
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-track { background:var(--panel); }
::-webkit-scrollbar-thumb { background:var(--border); border-radius:5px; }
""")

_CSS = _CSS_TEMPLATE.substitute(
    BG=C_BG, PANEL=C_PANEL, CARD=C_CARD, CARD2=C_CARD2, HOVER=C_HOVER,
    BORDER=C_BORDER, ACCENT=C_ACCENT, ACCENT2=C_ACCENT2, TEXT=C_TEXT,
    DIM=C_DIM, SUCCESS=C_SUCCESS, WARNING=C_WARNING, DANGER=C_DANGER,
)

_JS = """
(function () {
  function activate(target) {
    document.querySelectorAll('.panel').forEach(function (p) {
      p.classList.toggle('active', p.id === target);
    });
    document.querySelectorAll('.nav-link').forEach(function (l) {
      l.classList.toggle('active', l.getAttribute('data-target') === target);
    });
    var content = document.querySelector('.content');
    if (content) content.scrollTop = 0;
  }

  document.querySelectorAll('.nav-link, .dash-row').forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.preventDefault();
      var target = el.getAttribute('data-target');
      if (!target) return;
      activate(target);
      var group = el.closest('.nav-group');
      if (group) group.classList.remove('collapsed');
    });
  });

  var search = document.getElementById('searchInput');
  if (search) {
    search.addEventListener('keyup', function () {
      var q = this.value.toLowerCase().trim();

      document.querySelectorAll('.nav-group').forEach(function (group) {
        var header = group.querySelector('.nav-group-header');
        var headerText = header ? header.textContent.toLowerCase() : '';
        var subLinks = group.querySelectorAll('.nav-sub .nav-link');
        var anyMatch = headerText.indexOf(q) !== -1;

        subLinks.forEach(function (link) {
          var match = q === '' || link.textContent.toLowerCase().indexOf(q) !== -1;
          link.parentElement.style.display = match ? '' : 'none';
          if (match) anyMatch = true;
        });

        group.style.display = anyMatch ? '' : 'none';
        if (q !== '' && anyMatch) group.classList.remove('collapsed');
      });

      document.querySelectorAll('.nav').forEach(function (nav) {
        Array.prototype.forEach.call(nav.children, function (li) {
          var link = li.querySelector('a.nav-link');
          if (!link || li.classList.contains('nav-group')) return;
          var match = q === '' || link.textContent.toLowerCase().indexOf(q) !== -1;
          li.style.display = match ? '' : 'none';
        });
      });
    });
  }
})();
"""


def _shell(title, sidebar_html, content_html, meta_html, brand):
    return (
        "<!DOCTYPE html>\n"
        '<html lang="pt-BR">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="topbar">\n'
        "  <div>\n"
        f'    <div class="brand">{_esc(brand)}</div>\n'
        f'    <div class="meta-line">{meta_html}</div>\n'
        "  </div>\n"
        '  <div class="search-box">\n'
        '    <input type="text" id="searchInput" placeholder="Filtrar navegacao...">\n'
        "  </div>\n"
        "</div>\n"
        '<div class="body-wrap">\n'
        f'  <nav class="sidebar">{sidebar_html}</nav>\n'
        f'  <main class="content">{content_html}</main>\n'
        "</div>\n"
        f"<script>{_JS}</script>\n"
        "</body>\n"
        "</html>\n"
    )


# ============================================================
# API PUBLICA
# ============================================================
def render_report(data, brand="Sek Optimize - System Analyzer"):
    """Gera o HTML (sidebar + conteudo) de uma unica maquina."""
    hostname  = _safe(data, "system", "hostname")
    username  = _safe(data, "system", "username")
    generated = data.get("generated_at", "N/A")
    schema_v  = data.get("schema_version", "N/A")

    sections = [k for k in data.keys() if k not in SKIP_KEYS]

    nav = ['<li><a class="nav-link active" data-target="overview" href="#">Dashboard</a></li>']
    for key in sections:
        nav.append(f'<li><a class="nav-link" data-target="{key}" href="#">{_esc(_title(key))}</a></li>')

    panels = [f'<section id="overview" class="panel active"><h2>Dashboard</h2>{_dashboard_html(data)}</section>']
    for key in sections:
        panels.append(
            f'<section id="{key}" class="panel">'
            f"<h2>{_esc(_title(key))}</h2>{_render_section(key, data[key])}"
            "</section>"
        )

    meta = (
        f"Hostname: <b>{_esc(hostname)}</b> &nbsp;|&nbsp; "
        f"Usuario: <b>{_esc(username)}</b> &nbsp;|&nbsp; "
        f"Gerado em: {_esc(generated)} &nbsp;|&nbsp; Schema v{_esc(schema_v)}"
    )

    return _shell(
        title=f"{brand} - {hostname}",
        sidebar_html=f'<ul class="nav">{"".join(nav)}</ul>',
        content_html="".join(panels),
        meta_html=meta,
        brand=brand,
    )


def render_consolidated(entries, brand="Sek Optimize - Relatorio Consolidado"):
    """
    Gera um HTML consolidado para varias maquinas.
    entries: lista de tuplas (label, data) — label e usado como fallback
             de hostname quando o JSON nao possui system.hostname.
    """
    nav_groups      = []
    panels          = []
    dashboard_rows  = []

    for i, (label, data) in enumerate(entries):
        hostname = _safe(data, "system", "hostname", default=label)
        username = _safe(data, "system", "username")
        os_ed    = _safe(data, "system", "os_edition", default=_safe(data, "system", "os"))
        cpu_m    = _safe(data, "cpu", "model", default=_safe(data, "cpu", "processor"))
        ram_gb   = _safe(data, "memory", "total_gb")

        stor     = data.get("storage", {}) or {}
        vols     = stor.get("volumes") or []
        disk_pct = vols[0].get("usage_pct", "N/A") if vols else "N/A"

        generated = data.get("generated_at", "N/A")
        sections  = [k for k in data.keys() if k not in SKIP_KEYS]

        sub_items = [f'<li><a class="nav-link" data-target="m{i}-overview" href="#">Dashboard</a></li>']
        for key in sections:
            sub_items.append(
                f'<li><a class="nav-link" data-target="m{i}-{key}" href="#">{_esc(_title(key))}</a></li>'
            )

        nav_groups.append(
            '<li class="nav-group collapsed">'
            f'<a class="nav-link nav-group-header" data-target="m{i}-overview" href="#">'
            f'<span class="arrow">&#9656;</span>{_esc(hostname)}</a>'
            f'<ul class="nav-sub">{"".join(sub_items)}</ul>'
            "</li>"
        )

        panels.append(
            f'<section id="m{i}-overview" class="panel">'
            f"<h2>{_esc(hostname)} &mdash; Dashboard</h2>{_dashboard_html(data, target_prefix=f'm{i}-')}"
            "</section>"
        )
        for key in sections:
            panels.append(
                f'<section id="m{i}-{key}" class="panel">'
                f"<h2>{_esc(hostname)} &mdash; {_esc(_title(key))}</h2>"
                f"{_render_section(key, data[key])}"
                "</section>"
            )

        dashboard_rows.append(
            f'<tr class="dash-row" data-target="m{i}-overview">'
            f"<td>{_esc(hostname)}</td><td>{_esc(username)}</td>"
            f"<td>{_esc(os_ed)}</td><td>{_esc(cpu_m)}</td>"
            f"<td>{_esc(ram_gb)} GB</td><td>{_esc(disk_pct)}%</td>"
            f"<td>{_esc(generated)}</td></tr>"
        )

    dashboard_panel = (
        '<section id="dashboard" class="panel active">'
        "<h2>Visao Geral Consolidada</h2>"
        f"<p class='meta-sub'>{len(entries)} maquina(s) neste relatorio. "
        "Clique em uma linha ou em uma maquina na barra lateral para ver os detalhes.</p>"
        '<div class="table-wrap"><table class="list dash-table">'
        "<thead><tr><th>Hostname</th><th>Usuario</th><th>Sistema</th>"
        "<th>CPU</th><th>RAM</th><th>Disco</th><th>Gerado em</th></tr></thead>"
        f"<tbody>{''.join(dashboard_rows)}</tbody>"
        "</table></div>"
        "</section>"
    )

    nav_html = (
        '<ul class="nav">'
        '<li><a class="nav-link active" data-target="dashboard" href="#">Dashboard</a></li>'
        f'{"".join(nav_groups)}'
        "</ul>"
    )

    return _shell(
        title=brand,
        sidebar_html=nav_html,
        content_html=dashboard_panel + "".join(panels),
        meta_html=f"{len(entries)} maquina(s) &nbsp;|&nbsp; Relatorio consolidado",
        brand=brand,
    )
