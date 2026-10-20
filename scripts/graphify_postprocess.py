#!/usr/bin/env python3
"""Limpia graphify-out/graph.json tras un /graphify.

El extractor AST de graphify produce falsos positivos en aristas `calls`:
  1. Llamadas a módulos de la librería estándar o externos (`json`, `sqlite3`,
     `os`…) tratados como funciones. Son nodos sin source_file.
  2. Autoaristas `calls` (source == target) cuando un método llama a una función
     de módulo con el mismo nombre (p. ej. `.pickDiversePalette()`).

Este script elimina esas aristas. Es idempotente: ejecutarlo dos veces no cambia
el resultado. Los nodos externos se conservan (siguen teniendo aristas `imports`).

Uso:
    python3 scripts/graphify_postprocess.py                  # limpia graph.json
    python3 scripts/graphify_postprocess.py --report         # + regenera GRAPH_REPORT.md
    python3 scripts/graphify_postprocess.py --html           # + regenera graph.html
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "graphify-out"
DEFAULT_GRAPH = OUT_DIR / "graph.json"


def _edge_list(data):
    """Devuelve la clave que usa el JSON para las aristas ("links" o "edges")."""
    return "links" if "links" in data else "edges"


def clean(data):
    """Quita falsos positivos de `calls`. Devuelve (datos limpios, estadísticas)."""
    key = _edge_list(data)
    nodes = {n["id"]: n for n in data["nodes"]}
    kept, stub_calls, self_calls = [], 0, 0
    for link in data[key]:
        if link.get("relation") == "calls":
            target = nodes.get(link["target"], {})
            if link["source"] == link["target"]:
                self_calls += 1
                continue
            if not target.get("source_file"):
                stub_calls += 1
                continue
        kept.append(link)
    cleaned = dict(data)
    cleaned[key] = kept
    stats = {
        "removed_stub_calls": stub_calls,
        "removed_self_calls": self_calls,
        "links_before": len(data[key]),
        "links_after": len(kept),
    }
    return cleaned, stats


def _write_json_atomic(path, data):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _graphify_python(out_dir):
    """Intérprete que tiene graphify instalado (el que escribió el skill)."""
    marker = out_dir / ".graphify_python"
    if marker.exists():
        return marker.read_text(encoding="utf-8").strip()
    return sys.executable


def _detection_from_graph(data, previous_report):
    """Resumen de corpus mínimo cuando no hay .graphify_detect.json."""
    import re

    files = {n["source_file"] for n in data["nodes"] if n.get("source_file")}
    words = 0
    if previous_report.exists():
        match = re.search(r"~([\d,]+) words", previous_report.read_text(encoding="utf-8"))
        if match:
            words = int(match.group(1).replace(",", ""))
    return {"total_files": len(files), "total_words": words, "files": {}}


def regenerate_report(out_dir=OUT_DIR):
    """Reescribe GRAPH_REPORT.md desde graph.json, con las mismas etiquetas de comunidad.

    Necesita graphify importable. Usa `.graphify_detect.json` si existe; si no,
    reconstruye el resumen de corpus (ver `_detection_from_graph`).
    """
    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.build import build_from_json
    from graphify.cluster import score_all
    from graphify.report import generate

    data = json.loads((out_dir / "graph.json").read_text(encoding="utf-8"))
    detect_path = out_dir / ".graphify_detect.json"
    if detect_path.exists():
        detection = json.loads(detect_path.read_text(encoding="utf-8"))
    else:
        # /graphify borra .graphify_detect.json al final de cada corrida. Sin él,
        # reconstruimos el resumen de corpus: archivos desde el grafo y palabras
        # desde la línea "~N words" del informe anterior.
        detection = _detection_from_graph(data, out_dir / "GRAPH_REPORT.md")
    labels_path = out_dir / ".graphify_labels.json"
    labels = {int(k): v for k, v in json.loads(labels_path.read_text(encoding="utf-8")).items()} if labels_path.exists() else {}

    tokens = {"input": 0, "output": 0}
    extract_path = out_dir / ".graphify_extract.json"
    if extract_path.exists():
        extract = json.loads(extract_path.read_text(encoding="utf-8"))
        tokens = {"input": extract.get("input_tokens", 0), "output": extract.get("output_tokens", 0)}

    G = build_from_json({
        "nodes": data["nodes"],
        "edges": data[_edge_list(data)],
        "hyperedges": data.get("hyperedges", []),
    })
    communities = {}
    for node_id, attrs in G.nodes(data=True):
        cid = attrs.get("community")
        if cid is not None:
            communities.setdefault(int(cid), []).append(node_id)
    for cid in communities:
        labels.setdefault(cid, f"Community {cid}")

    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, str(ROOT), suggested_questions=questions)
    (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    return "GRAPH_REPORT.md regenerado."


def export_html(out_dir=OUT_DIR):
    """Vuelve a generar graph.html con el comando de graphify."""
    result = subprocess.run(
        [_graphify_python(out_dir), "-m", "graphify", "export", "html"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return f"graph.html no regenerado: {result.stderr.strip() or result.stdout.strip()}"
    return "graph.html regenerado."


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH, help="ruta a graph.json")
    parser.add_argument("--report", action="store_true", help="regenerar GRAPH_REPORT.md")
    parser.add_argument("--html", action="store_true", help="regenerar graph.html")
    args = parser.parse_args(argv)

    data = json.loads(args.graph.read_text(encoding="utf-8"))
    cleaned, stats = clean(data)
    if stats["links_before"] != stats["links_after"]:
        _write_json_atomic(args.graph, cleaned)
    print(
        f"Aristas: {stats['links_before']} -> {stats['links_after']} "
        f"(calls a módulos externos quitados: {stats['removed_stub_calls']}, "
        f"autoaristas quitadas: {stats['removed_self_calls']})"
    )
    out_dir = args.graph.parent
    if args.report:
        print(regenerate_report(out_dir))
    if args.html:
        print(export_html(out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
