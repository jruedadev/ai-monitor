"""Dashboard HTML autocontenido, con pestañas por fuente + una vista 'Todo'."""
import json

_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Uso de IA por proyecto</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{
  --bg:#0b0e14; --panel:#12161f; --panel2:#171c27; --text:#e6e9ef; --muted:#8b95a7;
  --accent:#7c9eff; --border:#232938;
}
@media (prefers-color-scheme: light){
  :root{ --bg:#f5f6f8; --panel:#ffffff; --panel2:#f0f1f4; --text:#1a1d24; --muted:#5a6272; --border:#e2e4ea; }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:24px;}
h1{font-size:1.4rem;margin:0 0 4px}
.sub{color:var(--muted);font-size:.85rem;margin-bottom:20px}
.tabs{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.tab{padding:8px 14px;border-radius:8px;border:1px solid var(--border);background:var(--panel);cursor:pointer;font-size:.85rem}
.tab.active{background:var(--accent);color:#0b0e14;border-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px}
.card .label{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}
.card .value{font-size:1.5rem;font-weight:600;margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--border);border-radius:10px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;font-size:.85rem;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--panel2)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pname{max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.panel{display:none}
.panel.active{display:block}
.notice{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px;color:var(--muted)}
</style>
</head>
<body>
<h1>Uso de IA por proyecto</h1>
<div class="sub">Generado __GENERATED_AT__ · Claude Code · Codex · OpenCode · OpenRouter</div>

<div class="tabs" id="tabs"></div>
<div id="panels"></div>

<script>
const sources = __SOURCES__;
const combined = __COMBINED__;

const TAB_LABELS = {
  all: "Todo", claude_code: "Claude Code", codex: "Codex",
  opencode: "OpenCode", openrouter: "OpenRouter",
};

function fmtNum(n) { return (n || 0).toLocaleString(); }
function fmtCost(n) { return n == null ? "—" : "$" + n.toFixed(2); }

function renderProjectTable(data) {
  const rows = Object.entries(data).sort((a, b) => (b[1].total_tokens||0) - (a[1].total_tokens||0));
  const totalTokens = rows.reduce((s, [, v]) => s + (v.total_tokens || 0), 0);
  const totalCost = rows.reduce((s, [, v]) => s + (v.cost || 0), 0);
  let html = `<div class="grid">
    <div class="card"><div class="label">Proyectos</div><div class="value">${rows.length}</div></div>
    <div class="card"><div class="label">Tokens</div><div class="value">${fmtNum(totalTokens)}</div></div>
    <div class="card"><div class="label">Costo est.</div><div class="value">${fmtCost(totalCost)}</div></div>
  </div>`;
  html += `<table><thead><tr><th>Proyecto</th><th class="num">Tokens</th><th class="num">Costo</th>
    <th class="num">Msgs</th><th class="num">Sesiones</th></tr></thead><tbody>`;
  for (const [name, v] of rows) {
    html += `<tr><td class="pname" title="${name}">${name}</td>
      <td class="num">${fmtNum(v.total_tokens)}</td><td class="num">${fmtCost(v.cost)}</td>
      <td class="num">${v.messages || 0}</td><td class="num">${v.session_count || 0}</td></tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderOpenRouter(data) {
  if (data.unavailable) {
    return `<div class="notice">OpenRouter no disponible: ${data.reason}</div>`;
  }
  const rows = Object.entries(data.models || {}).sort((a, b) => b[1].tokens - a[1].tokens);
  let html = `<table><thead><tr><th>Modelo</th><th class="num">Tokens</th>
    <th class="num">Costo</th><th class="num">Requests</th></tr></thead><tbody>`;
  for (const [model, v] of rows) {
    html += `<tr><td class="pname" title="${model}">${model}</td>
      <td class="num">${fmtNum(v.tokens)}</td><td class="num">${fmtCost(v.cost)}</td>
      <td class="num">${v.requests}</td></tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

const tabsEl = document.getElementById('tabs');
const panelsEl = document.getElementById('panels');
const tabKeys = ['all', 'claude_code', 'codex', 'opencode', 'openrouter'];

tabKeys.forEach((key, i) => {
  const btn = document.createElement('button');
  btn.className = 'tab' + (i === 0 ? ' active' : '');
  btn.textContent = TAB_LABELS[key];
  btn.onclick = () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + key).classList.add('active');
  };
  tabsEl.appendChild(btn);

  const panel = document.createElement('div');
  panel.className = 'panel' + (i === 0 ? ' active' : '');
  panel.id = 'panel-' + key;
  if (key === 'all') panel.innerHTML = renderProjectTable(combined);
  else if (key === 'openrouter') panel.innerHTML = renderOpenRouter(sources.openrouter || {unavailable: true, reason: 'sin datos'});
  else panel.innerHTML = renderProjectTable(sources[key] || {});
  panelsEl.appendChild(panel);
});
</script>
</body>
</html>
"""


def render(sources, combined, generated_at):
    html = _HTML.replace("__GENERATED_AT__", generated_at)
    html = html.replace("__SOURCES__", json.dumps(sources))
    html = html.replace("__COMBINED__", json.dumps(combined))
    return html
