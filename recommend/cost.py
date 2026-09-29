"""Señales de costo persistidas como recomendaciones kind=costo (spec §3.4).
Reutiliza las RULES del briefing por fuente; el draft es texto determinista,
nunca pasa por el LLM."""
from urllib.parse import parse_qs, urlparse

import briefing

PERSISTED_RULES = (briefing.rule_spike_day, briefing.rule_project_concentration,
                   briefing.rule_subscription_missing)
IMPACT = {"warning": "alto", "info": "medio"}


def project_from_link(link):
    values = parse_qs(urlparse(link or "").query).get("proyecto")
    return values[0] if values else None


def _draft(signal, source, project):
    label = briefing.SOURCE_LABELS[source]
    if signal["id"] == "spike_day":
        return (f"Revisa el día marcado en {label} ({signal['link']} en el dashboard):\n"
                "1. Ordena las sesiones de ese día por costo y abre la más cara.\n"
                "2. Decide si fue un uso puntual o algo repetible (contexto muy largo, reintentos en bucle, "
                "modelo más caro de lo necesario).\n"
                "3. Si es repetible, fija una pauta: /compact antes de tareas largas o un modelo más barato "
                "para lo rutinario.")
    if signal["id"] == "project_concentration":
        name = project.rstrip("/").split("/")[-1] if project else "el proyecto"
        return (f"{name} concentra la mayor parte del gasto de {label} este mes. Opciones:\n"
                "1. Revisa sus sesiones más largas y qué contexto cargan en cada turno.\n"
                "2. Recorta el CLAUDE.md/AGENTS.md del proyecto a lo imprescindible.\n"
                "3. Usa un modelo más barato para tareas rutinarias de ese proyecto.")
    return ("Abre Configuración → ROI e indica el costo mensual y la fecha de inicio de tu plan "
            f"de {label}. Con eso el dashboard compara suscripción frente a precio de API.")


def cost_recommendations(project_rows, model_rows, settings, today, roots=None):
    out = []
    for source in briefing.PROJECT_SOURCES:
        ctx = briefing.build_context(project_rows, model_rows, settings, today, source, roots=roots)
        for rule in PERSISTED_RULES:
            signal = rule(ctx)
            if not signal:
                continue
            project = project_from_link(signal["link"])
            out.append({
                "tool": source,
                "tokens": briefing.sum_tokens(ctx["window_rows"]),
                "pattern": signal["title"][:120],
                "kind": "costo",
                "description": " · ".join(signal["evidence"])[:400],
                "impact": IMPACT.get(signal["severity"], "medio"),
                "evidence": {"rule": signal["id"], "items": signal["evidence"], "link": signal["link"],
                             "projects": [project] if project else [], "sources": [source]},
                "draft": _draft(signal, source, project),
                "signature": {"rule": signal["id"], "source": source, "project": project},
                "generator": "costo",
            })
    return out
