"""Capa LLM (spec §3.5): una sola llamada por corrida que agrupa candidatos
por significado y redacta una recomendación por grupo. Todo lo que devuelve
el modelo es dato no confiable: se valida, se redacta y se recorta aquí."""
import json
import os
import subprocess
import tempfile

from recommend.redact import redact
from recommend.settings import is_free, parse_entry

KINDS = ("skill", "plugin", "prompt")
TIMEOUT_SECONDS = 120
LIMITS = {"pattern": 120, "description": 400, "draft": 8000}
# El backend "claude" corre como llamada aislada y barata: sin herramientas, sin
# hooks/MCP/CLAUDE.md del usuario, sin slash commands y en Sonnet (no hereda el
# modelo por defecto de la sesión interactiva). Ver análisis de costo del
# subproyecto 3: sin estas flags, cada corrida heredaba ~30-40k tokens de
# sobrecarga del system prompt completo de Claude Code.
CLAUDE_SYSTEM_PROMPT = ("Analizas prompts repetidos de un desarrollador y devuelves "
                        "únicamente el objeto JSON pedido, sin texto adicional.")

INSTRUCTIONS = """Eres un asistente que analiza patrones repetidos en los prompts de un desarrollador.
Recibes una lista JSON de candidatos. Cada uno resume prompts parecidos: id, patrón, sesiones, días,
tokens, features y hasta 3 fragmentos (ya anonimizados).

Haz dos cosas:
1. Agrupa los candidatos que expresan la MISMA intención aunque usen palabras distintas. Un candidato
   solo puede estar en un grupo. Los que no se parecen a ningún otro pueden quedar fuera.
2. Para cada grupo, clasifica y redacta UNA recomendación:
   - "skill": el usuario repite los mismos pasos; propón un SKILL.md con frontmatter (name, description) y pasos.
   - "plugin": el usuario pega a mano datos de un servicio externo; propón conectar un servidor MCP.
   - "prompt": el usuario repite instrucciones; propón una sección para CLAUDE.md o AGENTS.md.

No calcules cifras: sesiones, tokens e impacto se calculan aparte. Escribe en español.
Responde SOLO con un objeto JSON con esta forma exacta, sin texto adicional:
{"groups":[{"group_id":"g1","members":["c3","c7"]}],
 "recommendations":[{"group_id":"g1","kind":"skill|plugin|prompt","pattern":"título corto",
                     "description":"por qué conviene (máx. 400 caracteres)","draft":"borrador listo para copiar"}]}"""


class AttemptError(Exception):
    """Un intento falló; run_llm pasa al siguiente modelo de la cadena."""


def candidate_payload(c):
    ev = c.evidence()
    return {"id": c.cluster_id, "pattern": c.pattern, "sessions": ev["sessions"], "days": ev["days"],
            "tokens": ev["tokens"], "features": c.features, "snippets": ev["snippets"]}


def build_prompt(candidates):
    payload = json.dumps([candidate_payload(c) for c in candidates], ensure_ascii=False, indent=1)
    return f"{INSTRUCTIONS}\n\nCandidatos:\n{payload}\n"


def extract_json(text):
    """Del primer '{' al último '}': tolera prosa y cercas ```json alrededor."""
    if not isinstance(text, str):
        raise ValueError("La respuesta no es texto")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("La respuesta no contiene un objeto JSON")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("La respuesta no es un objeto JSON")
    return data


def check_schema(data):
    if not isinstance(data.get("groups"), list) or not isinstance(data.get("recommendations"), list):
        raise ValueError("La respuesta no tiene groups y recommendations como listas")


def validate_groups(data, ids):
    known, claimed, groups = set(ids), set(), {}
    for group in data.get("groups", []):
        if not isinstance(group, dict):
            continue
        gid, members = group.get("group_id"), group.get("members")
        if not isinstance(gid, str) or not gid or gid in groups or not isinstance(members, list) or not members:
            continue
        if len(set(map(str, members))) != len(members):
            continue
        if any(not isinstance(m, str) or m not in known or m in claimed for m in members):
            continue
        claimed.update(members)
        groups[gid] = list(members)
    for cid in ids:
        if cid not in claimed:
            groups[cid if cid not in groups else f"{cid}-solo"] = [cid]
    return groups


def _clean(value, limit):
    if not isinstance(value, str) or not value.strip():
        return None
    return redact(value.strip())[:limit]


def validate_recommendations(data, group_ids):
    out = {}
    for rec in data.get("recommendations", []):
        if not isinstance(rec, dict):
            continue
        gid = rec.get("group_id")
        if not isinstance(gid, str) or gid not in group_ids or gid in out or rec.get("kind") not in KINDS:
            continue
        fields = {key: _clean(rec.get(key), limit) for key, limit in LIMITS.items()}
        if None in fields.values():
            continue
        out[gid] = {"kind": rec["kind"], **fields}
    return out


def subprocess_runner(args, cwd, timeout):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _call(runner, args, cwd):
    try:
        code, stdout, stderr = runner(args, cwd, TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise AttemptError(f"timeout de {TIMEOUT_SECONDS} s") from None
    except OSError as exc:
        raise AttemptError(f"no se pudo ejecutar: {exc}") from None
    if code != 0:
        raise AttemptError(f"salió con código {code}: {(stderr or '').strip()[:200]}")
    return stdout


def _parse(text):
    try:
        data = extract_json(text)
        check_schema(data)
    except ValueError as exc:
        raise AttemptError(f"JSON inválido: {exc}") from None
    return data


def _hermes_attempt(prompt, entry, runner, cwd):
    try:
        provider, model = parse_entry(entry)
    except ValueError as exc:
        raise AttemptError(str(exc)) from None
    if not is_free(model):
        raise AttemptError("con Hermes solo se permiten modelos free")
    fd, usage_path = tempfile.mkstemp(prefix="usage-", suffix=".json", dir=cwd)
    os.close(fd)
    os.unlink(usage_path)  # Hermes lo crea; si no aparece, el intento falla
    try:
        stdout = _call(runner, ["hermes", "-z", prompt, "--provider", provider, "-m", model,
                                "--ignore-rules", "--safe-mode", "--usage-file", usage_path], cwd)
        try:
            with open(usage_path) as fh:
                usage = json.load(fh)
        except (OSError, ValueError):
            raise AttemptError("Hermes no escribió el usage-file") from None
        if not isinstance(usage, dict) or usage.get("failed"):
            raise AttemptError("Hermes reportó failed en el usage-file")
        try:
            cost = float(usage.get("estimated_cost_usd") or 0)
            tokens = int(usage.get("total_tokens") or 0)
        except (TypeError, ValueError):
            raise AttemptError("usage-file con valores no numéricos") from None
        if cost > 0:
            raise AttemptError(f"costo {cost} > 0 con un modelo que debía ser free")
        return _parse(stdout), tokens, cost
    finally:
        if os.path.exists(usage_path):
            os.unlink(usage_path)


def _claude_attempt(prompt, runner, cwd):
    stdout = _call(runner, ["claude", "-p", prompt, "--output-format", "json",
                            "--model", "sonnet", "--tools", "", "--strict-mcp-config",
                            "--disable-slash-commands", "--setting-sources", "",
                            "--system-prompt", CLAUDE_SYSTEM_PROMPT], cwd)
    try:
        envelope = json.loads(stdout)
    except ValueError:
        raise AttemptError("salida de claude -p no es JSON") from None
    if not isinstance(envelope, dict) or envelope.get("is_error"):
        raise AttemptError(f"claude -p devolvió error: {str(envelope.get('result', ''))[:200]}"
                           if isinstance(envelope, dict) else "salida de claude -p inesperada")
    usage = envelope.get("usage") or {}
    tokens = sum(int(usage.get(key) or 0) for key in
                 ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return _parse(envelope.get("result")), tokens, float(envelope.get("total_cost_usd") or 0)


def run_llm(candidates, backend, chain, runner=subprocess_runner, cwd="."):
    prompt = build_prompt(candidates)
    result = {"ok": False, "data": None, "model": None, "attempts": 0, "errors": [],
              "llm_tokens": 0, "llm_cost": 0.0}
    plan = [(entry, lambda e=entry: _hermes_attempt(prompt, e, runner, cwd)) for entry in chain] \
        if backend == "hermes" else [("claude", lambda: _claude_attempt(prompt, runner, cwd))]
    for label, attempt in plan:
        result["attempts"] += 1
        try:
            data, tokens, cost = attempt()
        except AttemptError as exc:
            result["errors"].append(f"{label}: {exc}")
            continue
        result.update(ok=True, data=data, model=label, llm_tokens=tokens, llm_cost=cost)
        break
    return result
