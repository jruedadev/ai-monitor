"""Recomendación local sin LLM (spec §3.6). generator = "reglas". Las
corridas siguientes con LLM enriquecen estos registros (store.apply_run)."""
from recommend.cluster import normalize
from recommend.redact import redact

LIMITS = {"pattern": 120, "description": 400, "draft": 8000}
_SLUG_WORDS = 5


def classify(features):
    if features.get("menciona_servicio") and features.get("pega_datos"):
        return "plugin"
    if features.get("mismos_pasos"):
        return "skill"
    return "prompt"


def _slug(pattern):
    words = normalize(pattern)[:_SLUG_WORDS]
    return "-".join(words) if words else "patron-repetido"


def _summary(ev):
    return f"Se repite en {ev['sessions']} sesiones durante {ev['days']} días ({ev['tokens']:,} tokens)".replace(",", ".")


def _skill(c, ev):
    steps = c.common_steps()
    lines = [f"{i}. {step.capitalize()} …" for i, step in enumerate(steps, start=1)] or \
            ["1. Describe aquí el primer paso que repites."]
    description = f"{_summary(ev)} y sigue siempre los mismos pasos. Una skill los deja escritos una sola vez."
    draft = (f"---\nname: {_slug(c.pattern)}\n"
             f"description: Úsala cuando pidas algo como \"{c.pattern[:80]}\".\n---\n\n"
             f"# {c.pattern}\n\nPasos:\n" + "\n".join(lines) + "\n")
    return description, draft


def _plugin(c, ev):
    svc = c.features["menciona_servicio"][0]
    description = (f"{_summary(ev)}. Pegas a mano datos de {svc}; un servidor MCP de {svc} "
                   "los traería directamente a la sesión.")
    draft = (f"# Conectar {svc} por MCP\n\n"
             f"1. Busca el servidor MCP oficial (o uno mantenido por la comunidad) para {svc}.\n"
             "2. Regístralo en Claude Code:\n\n"
             f"   claude mcp add {svc} -- <comando del servidor MCP de {svc}>\n\n"
             f"3. En vez de pegar el contenido, pide: \"consulta en {svc} …\".\n")
    return description, draft


def _prompt(c, ev):
    reason = ("Pegas datos a mano (logs, trazas o JSON) con las mismas indicaciones"
              if c.features.get("pega_datos") else "Repites las mismas indicaciones")
    description = f"{_summary(ev)}. {reason}; guárdalas en CLAUDE.md o AGENTS.md para no escribirlas cada vez."
    examples = "\n".join(f"- {s.splitlines()[0]}" for s in c.snippets())
    draft = (f"## {c.pattern}\n\n"
             "Cuando te pida algo como lo siguiente, aplica siempre estas pautas sin que tenga que repetirlas:\n\n"
             "- (escribe aquí las pautas que hoy repites en cada prompt)\n\n"
             f"Ejemplos de cómo lo pido:\n{examples}\n\n"
             "Guarda este bloque en CLAUDE.md o AGENTS.md del proyecto.\n")
    return description, draft


_BUILDERS = {"skill": _skill, "plugin": _plugin, "prompt": _prompt}


def recommend(c):
    kind = classify(c.features)
    ev = c.evidence()
    description, draft = _BUILDERS[kind](c, ev)
    return {
        "kind": kind,
        "pattern": redact(c.pattern)[:LIMITS["pattern"]],
        "description": redact(description)[:LIMITS["description"]],
        "draft": redact(draft)[:LIMITS["draft"]],
        "generator": "reglas",
    }
