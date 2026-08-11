#!/usr/bin/env python3
"""Agrega el uso de tokens de Claude Code por proyecto, leyendo los
transcripts locales en ~/.claude/projects/*/*.jsonl.

Uso:
  claude_usage.py               -> resumen en terminal (tabla)
  claude_usage.py --json         -> vuelca el agregado en JSON (stdout)
  claude_usage.py --html out.html -> genera dashboard HTML autocontenido
"""
import json
import os
import sys
import glob
import argparse
from collections import defaultdict
from datetime import datetime, timezone

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")

# Precios aproximados USD por millón de tokens (input / output / cache_read / cache_write)
# Ajustar si cambian los precios publicados por Anthropic.
PRICING = {
    "claude-opus-5":        {"in": 15.0, "out": 75.0, "cache_r": 1.5,  "cache_w": 18.75},
    "claude-sonnet-5":      {"in": 3.0,  "out": 15.0, "cache_r": 0.3,  "cache_w": 3.75},
    "claude-haiku-4-5-20251001": {"in": 1.0, "out": 5.0, "cache_r": 0.1, "cache_w": 1.25},
    "claude-fable-5":       {"in": 3.0,  "out": 15.0, "cache_r": 0.3,  "cache_w": 3.75},
}
DEFAULT_PRICE = {"in": 3.0, "out": 15.0, "cache_r": 0.3, "cache_w": 3.75}


def price_for(model):
    if not model:
        return DEFAULT_PRICE
    for key, p in PRICING.items():
        if key in model:
            return p
    return DEFAULT_PRICE


def cost_of(usage, model):
    p = price_for(model)
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    cw = usage.get("cache_creation_input_tokens", 0) or 0
    return (inp * p["in"] + out * p["out"] + cr * p["cache_r"] + cw * p["cache_w"]) / 1_000_000


def project_name_from_dir(dirname, cwd_hint=None):
    # Preferimos el cwd real capturado en los registros (no ambiguo);
    # si no hay, mostramos el nombre de directorio codificado tal cual.
    return cwd_hint or dirname


def collect():
    projects = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "cost": 0.0, "messages": 0, "sessions": set(),
        "by_day": defaultdict(lambda: {"tokens": 0, "cost": 0.0}),
        "sessions_detail": defaultdict(lambda: {
            "tokens": 0, "cost": 0.0, "title": None, "last_ts": None, "cwd": None
        }),
    })

    dirs = sorted(glob.glob(os.path.join(PROJECTS_DIR, "*")))
    for d in dirs:
        if not os.path.isdir(d):
            continue
        dname = os.path.basename(d)
        for jf in glob.glob(os.path.join(d, "*.jsonl")):
            session_id = os.path.basename(jf).replace(".jsonl", "")
            with open(jf, "r", errors="ignore") as fh:
                lines = fh.readlines()

            # Pre-pasada: resolver el cwd real de la sesión (más legible que el
            # nombre de directorio codificado) y capturar títulos ai-title.
            resolved_name = dname
            title_for_session = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") == "ai-title" and rec.get("aiTitle"):
                    title_for_session = rec["aiTitle"]
                if rec.get("cwd"):
                    resolved_name = rec["cwd"]
                    break

            if title_for_session:
                projects[resolved_name]["sessions_detail"][session_id]["title"] = title_for_session

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                rtype = rec.get("type")
                if rtype != "assistant":
                    continue

                msg = rec.get("message") or {}
                usage = msg.get("usage")
                if not usage:
                    continue

                model = msg.get("model")
                ts = rec.get("timestamp")
                cwd = rec.get("cwd")

                inp = usage.get("input_tokens", 0) or 0
                out = usage.get("output_tokens", 0) or 0
                cr = usage.get("cache_read_input_tokens", 0) or 0
                cw = usage.get("cache_creation_input_tokens", 0) or 0
                total_tok = inp + out + cr + cw
                c = cost_of(usage, model)

                p = projects[resolved_name]
                p["input"] += inp
                p["output"] += out
                p["cache_read"] += cr
                p["cache_write"] += cw
                p["cost"] += c
                p["messages"] += 1
                p["sessions"].add(session_id)

                day = ts[:10] if ts else "unknown"
                p["by_day"][day]["tokens"] += total_tok
                p["by_day"][day]["cost"] += c

                sd = p["sessions_detail"][session_id]
                sd["tokens"] += total_tok
                sd["cost"] += c
                sd["cwd"] = cwd or sd["cwd"]
                if ts and (sd["last_ts"] is None or ts > sd["last_ts"]):
                    sd["last_ts"] = ts

    # serializar sets
    out = {}
    for dname, p in projects.items():
        out[dname] = {
            "input": p["input"],
            "output": p["output"],
            "cache_read": p["cache_read"],
            "cache_write": p["cache_write"],
            "total_tokens": p["input"] + p["output"] + p["cache_read"] + p["cache_write"],
            "cost": round(p["cost"], 4),
            "messages": p["messages"],
            "session_count": len(p["sessions"]),
            "by_day": {k: {"tokens": v["tokens"], "cost": round(v["cost"], 4)} for k, v in p["by_day"].items()},
            "sessions_detail": [
                {"session_id": sid, "tokens": v["tokens"], "cost": round(v["cost"], 4),
                 "title": v["title"], "last_ts": v["last_ts"], "cwd": v["cwd"]}
                for sid, v in p["sessions_detail"].items()
            ],
        }
    return out


def print_table(data):
    rows = sorted(data.items(), key=lambda kv: kv[1]["total_tokens"], reverse=True)
    total_tokens = sum(v["total_tokens"] for _, v in rows)
    total_cost = sum(v["cost"] for _, v in rows)

    name_w = max([len(k) for k, _ in rows] + [7])
    header = f"{'PROYECTO':<{name_w}}  {'TOKENS':>12}  {'COSTO $':>10}  {'MSGS':>6}  {'SESIONES':>8}"
    print(header)
    print("-" * len(header))
    for name, v in rows:
        print(f"{name:<{name_w}}  {v['total_tokens']:>12,}  {v['cost']:>10.2f}  {v['messages']:>6}  {v['session_count']:>8}")
    print("-" * len(header))
    print(f"{'TOTAL':<{name_w}}  {total_tokens:>12,}  {total_cost:>10.2f}")
    print("\n(Costo estimado con precios de lista; no incluye descuentos de plan/suscripción.)")

    print("\nTareas/sesiones más pesadas (top 10 por tokens):")
    all_sessions = []
    for pname, v in data.items():
        for s in v["sessions_detail"]:
            s2 = dict(s)
            s2["project"] = pname
            all_sessions.append(s2)
    all_sessions.sort(key=lambda s: s["tokens"], reverse=True)
    for s in all_sessions[:10]:
        title = s["title"] or s["session_id"][:8]
        print(f"  {s['tokens']:>10,} tok  ${s['cost']:>7.2f}  {s['project']}  — {title}")


def generate_html(data, out_path):
    payload = json.dumps(data)
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    html = HTML_TEMPLATE.replace("__DATA__", payload).replace("__GENERATED_AT__", generated_at)
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Dashboard generado en: {out_path}")


HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Uso de Claude por proyecto</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{
  --bg:#0b0e14; --panel:#12161f; --panel2:#171c27; --text:#e6e9ef; --muted:#8b95a7;
  --accent:#7c9eff; --accent2:#63d2a5; --border:#232938;
}
@media (prefers-color-scheme: light){
  :root{ --bg:#f5f6f8; --panel:#ffffff; --panel2:#f0f1f4; --text:#1a1d24; --muted:#5a6272; --border:#e2e4ea; }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:24px;}
h1{font-size:1.4rem;margin:0 0 4px}
.sub{color:var(--muted);font-size:.85rem;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px}
.card .label{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}
.card .value{font-size:1.5rem;font-weight:600;margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--border);border-radius:10px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;font-size:.85rem;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600;cursor:pointer;user-select:none}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--panel2)}
.bar{height:6px;border-radius:3px;background:var(--accent);margin-top:6px}
section{margin-bottom:28px}
h2{font-size:1rem;margin:0 0 10px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pname{max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
</head>
<body>
<h1>Uso de Claude Code por proyecto</h1>
<div class="sub">Generado __GENERATED_AT__ · datos de ~/.claude/projects/*.jsonl · costo estimado con precios de lista</div>

<div class="grid" id="summary"></div>

<section>
<h2>Por proyecto</h2>
<table id="projTable">
<thead><tr>
<th data-k="name">Proyecto</th><th data-k="total_tokens" class="num">Tokens</th>
<th data-k="cost" class="num">Costo est.</th><th data-k="messages" class="num">Msgs</th>
<th data-k="session_count" class="num">Sesiones</th>
</tr></thead>
<tbody></tbody>
</table>
</section>

<section>
<h2>Tareas / sesiones más pesadas</h2>
<table id="sessTable">
<thead><tr>
<th>Título / sesión</th><th>Proyecto</th><th class="num">Tokens</th><th class="num">Costo est.</th><th>Última actividad</th>
</tr></thead>
<tbody></tbody>
</table>
</section>

<script>
const data = __DATA__;

const rows = Object.entries(data).map(([name, v]) => ({name, ...v}));
rows.sort((a,b)=>b.total_tokens - a.total_tokens);

const totalTokens = rows.reduce((s,r)=>s+r.total_tokens,0);
const totalCost = rows.reduce((s,r)=>s+r.cost,0);
const totalMsgs = rows.reduce((s,r)=>s+r.messages,0);
const totalSessions = rows.reduce((s,r)=>s+r.session_count,0);

document.getElementById('summary').innerHTML = `
  <div class="card"><div class="label">Proyectos</div><div class="value">${rows.length}</div></div>
  <div class="card"><div class="label">Tokens totales</div><div class="value">${totalTokens.toLocaleString()}</div></div>
  <div class="card"><div class="label">Costo estimado</div><div class="value">$${totalCost.toFixed(2)}</div></div>
  <div class="card"><div class="label">Mensajes</div><div class="value">${totalMsgs.toLocaleString()}</div></div>
  <div class="card"><div class="label">Sesiones</div><div class="value">${totalSessions}</div></div>
`;

const maxTok = Math.max(...rows.map(r=>r.total_tokens), 1);
const tbody = document.querySelector('#projTable tbody');
tbody.innerHTML = rows.map(r => `
  <tr>
    <td class="pname" title="${r.name}">${r.name}
      <div class="bar" style="width:${(r.total_tokens/maxTok*100).toFixed(1)}%"></div>
    </td>
    <td class="num">${r.total_tokens.toLocaleString()}</td>
    <td class="num">$${r.cost.toFixed(2)}</td>
    <td class="num">${r.messages}</td>
    <td class="num">${r.session_count}</td>
  </tr>
`).join('');

let allSessions = [];
for (const [pname, v] of Object.entries(data)) {
  for (const s of v.sessions_detail) allSessions.push({...s, project: pname});
}
allSessions.sort((a,b)=>b.tokens - a.tokens);
allSessions = allSessions.slice(0, 30);

document.querySelector('#sessTable tbody').innerHTML = allSessions.map(s => `
  <tr>
    <td class="pname" title="${s.session_id}">${s.title || s.session_id.slice(0,8)}</td>
    <td class="pname" title="${s.project}">${s.project}</td>
    <td class="num">${s.tokens.toLocaleString()}</td>
    <td class="num">$${s.cost.toFixed(2)}</td>
    <td>${s.last_ts ? new Date(s.last_ts).toLocaleString() : '—'}</td>
  </tr>
`).join('');
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Vuelca el agregado en JSON")
    ap.add_argument("--html", metavar="OUT", help="Genera dashboard HTML en la ruta dada")
    args = ap.parse_args()

    data = collect()

    if args.html:
        generate_html(data, args.html)
    elif args.json:
        print(json.dumps(data, indent=2))
    else:
        print_table(data)


if __name__ == "__main__":
    main()
