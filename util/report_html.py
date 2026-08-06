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

SECTION_TITLES = {
    "system":             "Sistema",
    "bios":               "BIOS",
    "motherboard":        "Placa Mae",
    "cpu":                "CPU",
    "memory":             "Memoria RAM",
    "storage":             "Armazenamento",
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


def _progress_bar(pct):
    try:
        pct_f = float(pct)
    except (TypeError, ValueError):
        pct_f = 0.0
    pct_f = max(0.0, min(100.0, pct_f))
    if pct_f < 70:
        color = C_SUCCESS
    elif pct_f < 90:
        color = C_WARNING
    else:
        color = C_DANGER
    return (
        f"<div class='progress'><div class='progress-bar' "
        f"style='width:{pct_f}%;background:{color}'></div></div>"
        f"<small>{_esc(pct)}% uso</small>"
    )


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


def _overview_html(data):
    sysd = data.get("system", {}) or {}
    cpud = data.get("cpu", {}) or {}
    memd = data.get("memory", {}) or {}
    stor = data.get("storage", {}) or {}
    runtime = data.get("runtime", {}) or {}

    volumes = stor.get("volumes") or []
    vol0    = volumes[0] if volumes else {}
    drives  = stor.get("drives") or []
    drive0  = drives[0] if drives else {}

    cpu_pct  = runtime.get("cpu_usage_pct", 0)
    ram_pct  = memd.get("usage_pct", 0)
    disk_pct = vol0.get("usage_pct", 0)

    return f"""
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
        </div>
    </div>
    """


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
.dim { color:var(--dim); }
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

    nav = ['<li><a class="nav-link active" data-target="overview" href="#">Visao Geral</a></li>']
    for key in sections:
        nav.append(f'<li><a class="nav-link" data-target="{key}" href="#">{_esc(_title(key))}</a></li>')

    panels = [f'<section id="overview" class="panel active"><h2>Visao Geral</h2>{_overview_html(data)}</section>']
    for key in sections:
        panels.append(
            f'<section id="{key}" class="panel">'
            f"<h2>{_esc(_title(key))}</h2>{_render_section_body(data[key])}"
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

        sub_items = [f'<li><a class="nav-link" data-target="m{i}-overview" href="#">Visao Geral</a></li>']
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
            f"<h2>{_esc(hostname)} &mdash; Visao Geral</h2>{_overview_html(data)}"
            "</section>"
        )
        for key in sections:
            panels.append(
                f'<section id="m{i}-{key}" class="panel">'
                f"<h2>{_esc(hostname)} &mdash; {_esc(_title(key))}</h2>"
                f"{_render_section_body(data[key])}"
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
