# Parametrización de carpetas y onboarding inicial — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sustituir la carpeta `DEV` fija por raíces de cliente configurables, guardadas en `history.db`, y añadir un onboarding `/bienvenida` que crea los ajustes de carpetas, ROI y motor la primera vez.

**Architecture:** `client_of(path, roots)` se vuelve una función pura con un port idéntico en Python (`clients.py`) y TypeScript (`lib/clients.ts`), atada por un fixture JSON compartido. `history.py` persiste `client_roots` y `onboarding_completed_at` en la tabla `app_settings`; `briefing.py` la lee en solo lectura y `server.py` la expone en `/api/app-settings`. En el frontend, un `AppSettingsProvider` reparte las raíces a todos los consumidores y `App.tsx` redirige a `/bienvenida` mientras el onboarding no se haya completado.

**Tech Stack:**
- Backend: Python 3 stdlib (`sqlite3`, `json`, `shutil`, `unittest`).
- Frontend: Vite + React 19 + TypeScript + Tailwind v4 + shadcn/base-ui + react-router 7 + vitest.

**Spec:** `docs/superpowers/specs/2026-09-29-carpetas-onboarding-design.md`

## Global Constraints

- **Backend solo stdlib**: `server.py`, `history.py`, `briefing.py`, `clients.py` y `collectors/` no usan dependencias externas.
- **Portabilidad**: ningún archivo del repo contiene rutas del autor (`/home/jruedadev`, `~/DEV/JRDV`). En tests y fixtures se usan rutas ficticias como `/home/u/...` o `/srv/...`.
- **`history.db` nunca se poda**: solo `INSERT OR REPLACE`, nunca `DELETE`.
- **`briefing.py` abre `history.db` en solo lectura** (`mode=ro`): nunca la crea ni la modifica.
- **Graceful degradation**: un `sqlite3.Error` nunca produce un 500 en los GET de ajustes; se responde con valores por defecto y `degraded: true`.
- **Valor por defecto** de raíces: `[{"root": "DEV", "mode": "cliente"}]`. Con él, la agrupación tiene que ser idéntica a la actual.
- **Límites de raíces**: de 1 a 20 raíces; `root` con 200 caracteres como máximo; `mode` ∈ {`cliente`, `plano`}.
- **Texto de UI** en español, con tildes.
- **Commits** sin `Co-Authored-By: Claude` ni `Claude-Session`.
- **Suite backend**: `env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests` (desde la raíz del repo).
- **Verificación frontend**: `cd frontend && npx vitest run && npx oxlint && npx tsc -b --noEmit && npm run build`.

## Review Focus

1. **Raíz absoluta con prefijo parecido.** `/srv/trabajo2/x` **no** debe coincidir con la raíz `/srv/trabajo`; un `startsWith` ingenuo sí coincidiría. Cubierto por un caso del fixture (Task 1).
2. **Error de red, o server viejo sin `/api/app-settings`.** El usuario no puede quedar atrapado en `/bienvenida`: sin ajustes cargados, no se redirige. Cubierto en `shouldRedirectToOnboarding` (Task 5).
3. **Mayúsculas duplicadas entre sugerencias** (`DEV` y `dev` en proyectos distintos). `suggestRoots` debe proponer una sola raíz; si no, el `POST` falla por duplicado. Cubierto en Task 5.
4. **Fila vacía mientras el usuario edita raíces** (acaba de pulsar "Añadir"). La vista previa no debe romperse ni contar esa fila. Cubierto en `previewClients` (Task 1).
5. **Fallo a mitad de Finalizar** (por ejemplo, el ROI da 400). No se debe marcar el onboarding como completado y hay que indicar qué paso falló. Cubierto en `saveOnboarding` (Task 5).

---

## Estructura de archivos

**Nuevos**
- `clients.py`: `client_of`, `normalize_roots`, `parse_stored_roots`, `default_roots`, `ClientRootsError`. Módulo puro.
- `tests/test_clients.py`
- `tests/test_app_settings.py`
- `frontend/src/lib/onboarding.ts`: `shouldRedirectToOnboarding`, `suggestRoots`, `suggestBackend`, `saveOnboarding`, `skipDraft`.
- `frontend/src/lib/onboarding.test.ts`
- `frontend/src/lib/roiDraft.ts`: `RoiDraft`, `toRoiDraft`, `roiPayload`, `plansWithData`.
- `frontend/src/lib/roiDraft.test.ts`
- `frontend/src/hooks/appSettingsContext.ts`: el contexto y los hooks `useAppSettings` y `useClientRoots`.
- `frontend/src/components/AppSettingsProvider.tsx`
- `frontend/src/components/RoiFields.tsx`
- `frontend/src/components/ClientRootsEditor.tsx`
- `frontend/src/components/ClientRootsForm.tsx`
- `frontend/src/views/OnboardingView.tsx`

**Modificados**
- `tests/fixtures/client_of_cases.json`
- `briefing.py`
- `history.py`
- `server.py`
- `tests/test_briefing.py`
- `tests/test_server_recommendations.py`
- `frontend/src/lib/clients.ts` y `clients.test.ts`
- `frontend/src/lib/projects.ts` y `projects.test.ts`
- `frontend/src/lib/commands.ts` y `commands.test.ts`
- `frontend/src/lib/routes.ts` y `routes.test.ts`
- `frontend/src/lib/settings.ts` y `settings.test.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/`: `TrendChart.tsx`, `SessionDetail.tsx`, `RoiView.tsx`, `CommandPalette.tsx`, `SettingsForm.tsx`
- `frontend/src/views/`: `ProjectsView.tsx`, `SpendView.tsx`, `SettingsView.tsx`
- `README.md`
- `CLAUDE.md`

---

### Task 1: `client_of` parametrizado en ambos lados + fixture compartido

**Files:**
- Create: `clients.py`, `tests/test_clients.py`
- Modify: `tests/fixtures/client_of_cases.json`, `briefing.py:200-206`, `tests/test_briefing.py:219-226`
- Modify: `frontend/src/lib/clients.ts`, `frontend/src/lib/clients.test.ts`
- Modify: consumidores del frontend, que por ahora pasan `DEFAULT_CLIENT_ROOTS`:
  - `lib/projects.ts`, `lib/projects.test.ts`
  - `lib/commands.ts`, `lib/commands.test.ts`
  - `App.tsx`
  - `components/TrendChart.tsx`, `components/SessionDetail.tsx`, `components/RoiView.tsx`, `components/CommandPalette.tsx`
  - `views/ProjectsView.tsx`, `views/SpendView.tsx`

**Interfaces:**
- Produces (Python, `clients.py`):
  - `OTHER = "Otros"`, `MODES = ("cliente", "plano")`, `MAX_ROOTS = 20`, `MAX_ROOT_CHARS = 200`
  - `class ClientRootsError(ValueError)`
  - `default_roots() -> list[dict]`: copia nueva de `[{"root": "DEV", "mode": "cliente"}]`
  - `client_of(path: str, roots: list[dict]) -> str`
  - `normalize_roots(value) -> list[dict]`: valida y normaliza; lanza `ClientRootsError`
  - `parse_stored_roots(raw: str | None) -> list[dict]`: JSON guardado → raíces; si es inválido, `default_roots()`
- Produces (TS, `lib/clients.ts`):
  - `type ClientRootMode = "cliente" | "plano"`, `interface ClientRoot { root: string; mode: ClientRootMode }`
  - `OTHER_CLIENT = "Otros"`, `MAX_CLIENT_ROOTS = 20`, `DEFAULT_CLIENT_ROOTS: ClientRoot[]`
  - `clientOf(path: string, roots: ClientRoot[]): string`
  - `groupProjectsByClient(paths: string[], roots: ClientRoot[]): Record<string, string[]>`
  - `previewClients(paths: string[], roots: ClientRoot[]): { clients: { name: string; count: number }[]; other: number }`
- Cambian de firma:
  - `projectsFor(sources, combined, source, client, roots: ClientRoot[])`
  - `buildCommandEntries(sources, combined, roots: ClientRoot[])`

- [ ] **Step 1: Reescribir el fixture compartido**

`tests/fixtures/client_of_cases.json` (completo):

```json
[
  {"roots": null, "path": "/home/u/DEV/GLOBEX/ai-monitor", "client": "GLOBEX"},
  {"roots": null, "path": "/home/u/dev/Acme/app", "client": "Acme"},
  {"roots": null, "path": "/home/u/Dev/Mixto/x", "client": "Mixto"},
  {"roots": null, "path": "/srv/DEV/A/DEV/B/app", "client": "A"},
  {"roots": null, "path": "/home/u/DEV", "client": "Otros"},
  {"roots": null, "path": "/home/u/projects/app", "client": "Otros"},
  {"roots": null, "path": "", "client": "Otros"},
  {"roots": [{"root": "proyectos", "mode": "plano"}], "path": "/home/u/proyectos/app", "client": "proyectos"},
  {"roots": [{"root": "/srv/trabajo", "mode": "plano"}], "path": "/srv/trabajo/app", "client": "trabajo"},
  {"roots": [{"root": "/srv/trabajo", "mode": "cliente"}], "path": "/srv/trabajo/Acme/app", "client": "Acme"},
  {"roots": [{"root": "/srv/trabajo", "mode": "cliente"}], "path": "/srv/trabajo2/Acme/app", "client": "Otros"},
  {"roots": [{"root": "/srv/trabajo", "mode": "cliente"}], "path": "/srv/trabajo", "client": "Otros"},
  {"roots": [{"root": "/Srv/trabajo", "mode": "plano"}], "path": "/srv/trabajo/app", "client": "Otros"},
  {"roots": [{"root": "work", "mode": "cliente"}], "path": "/home/u/WORK/Initech/api", "client": "Initech"},
  {"roots": [{"root": "clientes", "mode": "cliente"}, {"root": "DEV", "mode": "cliente"}], "path": "/home/u/DEV/clientes/Globex/app", "client": "Globex"},
  {"roots": [{"root": "DEV", "mode": "cliente"}, {"root": "clientes", "mode": "cliente"}], "path": "/home/u/DEV/clientes/Globex/app", "client": "clientes"}
]
```

`roots: null` significa "raíces por defecto".

- [ ] **Step 2: Escribir los tests de Python que fallan**

`tests/test_clients.py`:

```python
import json
import os
import unittest

import clients

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "client_of_cases.json")


class TestClientOf(unittest.TestCase):
    def test_shared_fixture_matches_clients_ts(self):
        with open(FIXTURE) as fh:
            cases = json.load(fh)
        for case in cases:
            roots = case["roots"] if case["roots"] is not None else clients.default_roots()
            with self.subTest(path=case["path"], roots=case["roots"]):
                self.assertEqual(clients.client_of(case["path"], roots), case["client"])

    def test_default_roots_is_a_fresh_copy(self):
        roots = clients.default_roots()
        roots[0]["root"] = "X"
        self.assertEqual(clients.default_roots(), [{"root": "DEV", "mode": "cliente"}])


class TestNormalizeRoots(unittest.TestCase):
    def test_strips_spaces_and_trailing_slash(self):
        self.assertEqual(
            clients.normalize_roots([{"root": "  DEV ", "mode": "cliente"}, {"root": "/srv/trabajo/", "mode": "plano"}]),
            [{"root": "DEV", "mode": "cliente"}, {"root": "/srv/trabajo", "mode": "plano"}],
        )

    def test_rejects_invalid_payloads(self):
        too_many = [{"root": f"r{i}", "mode": "cliente"} for i in range(21)]
        cases = {
            "no es lista": {"root": "DEV", "mode": "cliente"},
            "vacía": [],
            "demasiadas": too_many,
            "no es objeto": ["DEV"],
            "claves de más": [{"root": "DEV", "mode": "cliente", "x": 1}],
            "root no string": [{"root": 3, "mode": "cliente"}],
            "root vacío": [{"root": "   ", "mode": "cliente"}],
            "solo barra": [{"root": "/", "mode": "cliente"}],
            "nombre con barra": [{"root": "DEV/clientes", "mode": "cliente"}],
            "demasiado largo": [{"root": "a" * 201, "mode": "cliente"}],
            "modo inválido": [{"root": "DEV", "mode": "otro"}],
            "duplicado por mayúsculas": [{"root": "DEV", "mode": "cliente"}, {"root": "dev", "mode": "plano"}],
            "duplicado por barra final": [{"root": "/srv/x", "mode": "cliente"}, {"root": "/srv/x/", "mode": "plano"}],
        }
        for name, payload in cases.items():
            with self.subTest(name), self.assertRaises(clients.ClientRootsError):
                clients.normalize_roots(payload)

    def test_absolute_paths_keep_case_for_duplicates(self):
        roots = clients.normalize_roots([{"root": "/srv/X", "mode": "cliente"}, {"root": "/srv/x", "mode": "cliente"}])
        self.assertEqual(len(roots), 2)


class TestParseStoredRoots(unittest.TestCase):
    def test_valid_json(self):
        self.assertEqual(clients.parse_stored_roots('[{"root": "work", "mode": "plano"}]'),
                         [{"root": "work", "mode": "plano"}])

    def test_invalid_falls_back_to_default(self):
        for raw in (None, "", "{roto", "[]", '[{"root": "", "mode": "cliente"}]', '"DEV"'):
            with self.subTest(raw=raw):
                self.assertEqual(clients.parse_stored_roots(raw), clients.default_roots())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Ejecutar y ver que falla**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest tests.test_clients -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'clients'`.

- [ ] **Step 4: Implementar `clients.py`**

```python
"""Agrupación de proyectos por cliente según raíces configurables (spec 2026-09-29 §2).
Módulo puro: lo usan briefing.py e history.py. frontend/src/lib/clients.ts es su port
y tests/fixtures/client_of_cases.json el contrato compartido entre ambos."""
import json

OTHER = "Otros"
MODES = ("cliente", "plano")
MAX_ROOTS = 20
MAX_ROOT_CHARS = 200
_DEFAULT = ({"root": "DEV", "mode": "cliente"},)


class ClientRootsError(ValueError):
    """Lista de raíces inválida; history/server lo traducen a HTTP 400."""


def default_roots():
    return [dict(r) for r in _DEFAULT]


def _next_index(segments, root):
    """Índice del segmento que sigue a la raíz, o None si la raíz no coincide.
    Nombre: primera aparición, sin distinguir mayúsculas. Ruta absoluta: prefijo
    por segmentos completos (así /srv/trabajo2 no coincide con /srv/trabajo)."""
    if root.startswith("/"):
        prefix = root.rstrip("/").split("/")
        return len(prefix) if segments[:len(prefix)] == prefix else None
    target = root.upper()
    for idx, segment in enumerate(segments):
        if segment.upper() == target:
            return idx + 1
    return None


def client_of(path, roots):
    segments = path.split("/")
    for entry in roots:
        nxt = _next_index(segments, entry["root"])
        if nxt is None:
            continue
        if entry["mode"] == "plano":
            return entry["root"].rstrip("/").split("/")[-1]
        return segments[nxt] if nxt < len(segments) and segments[nxt] else OTHER
    return OTHER


def normalize_roots(value):
    if not isinstance(value, list):
        raise ClientRootsError("client_roots debe ser una lista")
    if not 1 <= len(value) <= MAX_ROOTS:
        raise ClientRootsError(f"client_roots debe tener entre 1 y {MAX_ROOTS} raíces")
    out, seen = [], set()
    for i, item in enumerate(value, start=1):
        if not isinstance(item, dict) or set(item) != {"root", "mode"}:
            raise ClientRootsError(f"Raíz {i}: debe tener exactamente root y mode")
        root, mode = item["root"], item["mode"]
        if not isinstance(root, str):
            raise ClientRootsError(f"Raíz {i}: root debe ser texto")
        root = root.strip()
        absolute = root.startswith("/")
        if absolute:
            root = root.rstrip("/")
            if not root:
                raise ClientRootsError(f"Raíz {i}: una ruta absoluta necesita al menos una carpeta")
        elif "/" in root:
            raise ClientRootsError(f"Raíz {i}: un nombre de carpeta no puede contener /; usa una ruta absoluta")
        if not root:
            raise ClientRootsError(f"Raíz {i}: root no puede estar vacío")
        if len(root) > MAX_ROOT_CHARS:
            raise ClientRootsError(f"Raíz {i}: root admite como máximo {MAX_ROOT_CHARS} caracteres")
        if mode not in MODES:
            raise ClientRootsError(f"Raíz {i}: mode debe ser cliente o plano")
        key = root if absolute else root.upper()
        if key in seen:
            raise ClientRootsError(f"Raíz {i}: {root} está repetida")
        seen.add(key)
        out.append({"root": root, "mode": mode})
    return out


def parse_stored_roots(raw):
    if raw is None:
        return default_roots()
    try:
        return normalize_roots(json.loads(raw))
    except (ValueError, TypeError):
        return default_roots()
```

(`ClientRootsError` y `json.JSONDecodeError` son subclases de `ValueError`.)

- [ ] **Step 5: Ejecutar y ver que pasa**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest tests.test_clients -v`
Expected: PASS.

- [ ] **Step 6: Delegar `briefing.client_of` y mover el test de paridad**

En `briefing.py`, añade `import clients` junto a `import history` y reemplaza `client_of` (líneas 200-206):

```python
def client_of(path, roots=None):
    """Cliente del proyecto según las raíces configuradas (clients.client_of)."""
    return clients.client_of(path, roots if roots is not None else clients.default_roots())
```

En `tests/test_briefing.py`, borra la clase `TestClientOfParity` completa (líneas 219-226), que ahora vive en `tests/test_clients.py`. Si `json` queda sin uso, quita el `import json` de ese archivo.

Run: `env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests`
Expected: todo OK.

- [ ] **Step 7: Escribir el test de TS que falla**

`frontend/src/lib/clients.test.ts` (completo):

```ts
import { describe, expect, it } from "vitest";
import cases from "../../../tests/fixtures/client_of_cases.json";
import { DEFAULT_CLIENT_ROOTS, clientOf, groupProjectsByClient, previewClients, type ClientRoot } from "@/lib/clients";

describe("clientOf: paridad con clients.client_of (fixture compartido)", () => {
  it.each(cases)("$path con $roots → $client", ({ roots, path, client }) => {
    expect(clientOf(path, (roots as ClientRoot[] | null) ?? DEFAULT_CLIENT_ROOTS)).toBe(client);
  });
});

describe("groupProjectsByClient", () => {
  it("agrupa según las raíces dadas", () => {
    const roots: ClientRoot[] = [{ root: "/srv/trabajo", mode: "plano" }];
    expect(groupProjectsByClient(["/srv/trabajo/a", "/srv/trabajo/b", "/tmp/c"], roots)).toEqual({
      trabajo: ["/srv/trabajo/a", "/srv/trabajo/b"],
      Otros: ["/tmp/c"],
    });
  });
});

describe("previewClients", () => {
  it("cuenta proyectos por cliente, separa Otros e ignora raíces vacías", () => {
    const roots: ClientRoot[] = [{ root: "DEV", mode: "cliente" }, { root: "  ", mode: "cliente" }];
    expect(previewClients(["/h/DEV/A/x", "/h/DEV/A/y", "/h/DEV/B/z", "/tmp/q"], roots)).toEqual({
      clients: [{ name: "A", count: 2 }, { name: "B", count: 1 }],
      other: 1,
    });
  });
  it("sin raíces útiles todo cae en Otros", () => {
    expect(previewClients(["/a/b"], [{ root: "", mode: "plano" }])).toEqual({ clients: [], other: 1 });
  });
});
```

Run: `cd frontend && npx vitest run src/lib/clients.test.ts`
Expected: FAIL (`previewClients` y `DEFAULT_CLIENT_ROOTS` no existen).

- [ ] **Step 8: Implementar `lib/clients.ts`**

```ts
/**
 * Cliente de un proyecto según raíces configurables (spec 2026-09-29 §2). Port de
 * clients.py; tests/fixtures/client_of_cases.json es el contrato compartido.
 */
export type ClientRootMode = "cliente" | "plano";

export interface ClientRoot {
  root: string;
  mode: ClientRootMode;
}

export const OTHER_CLIENT = "Otros";
export const MAX_CLIENT_ROOTS = 20;
export const DEFAULT_CLIENT_ROOTS: ClientRoot[] = [{ root: "DEV", mode: "cliente" }];

/** Índice del segmento que sigue a la raíz, o null. Ruta absoluta: prefijo por segmentos completos. */
function nextIndex(segments: string[], root: string): number | null {
  if (root.startsWith("/")) {
    const prefix = root.replace(/\/+$/, "").split("/");
    return prefix.every((part, i) => segments[i] === part) ? prefix.length : null;
  }
  const target = root.toUpperCase();
  const idx = segments.findIndex((s) => s.toUpperCase() === target);
  return idx === -1 ? null : idx + 1;
}

export function clientOf(projectPath: string, roots: ClientRoot[]): string {
  const segments = projectPath.split("/");
  for (const { root, mode } of roots) {
    const next = nextIndex(segments, root);
    if (next === null) continue;
    if (mode === "plano") return root.replace(/\/+$/, "").split("/").pop() || OTHER_CLIENT;
    return segments[next] || OTHER_CLIENT;
  }
  return OTHER_CLIENT;
}

export function groupProjectsByClient(paths: string[], roots: ClientRoot[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const path of paths) {
    (groups[clientOf(path, roots)] ??= []).push(path);
  }
  return groups;
}

/** Vista previa para el editor de raíces: ignora filas vacías (el usuario está escribiendo). */
export function previewClients(paths: string[], roots: ClientRoot[]): { clients: { name: string; count: number }[]; other: number } {
  const usable = roots.filter((r) => r.root.trim() !== "" && r.root.trim() !== "/");
  const groups = groupProjectsByClient(paths, usable);
  const other = groups[OTHER_CLIENT]?.length ?? 0;
  const clients = Object.entries(groups)
    .filter(([name]) => name !== OTHER_CLIENT)
    .map(([name, list]) => ({ name, count: list.length }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  return { clients, other };
}
```

Nota: `segments[next] || OTHER_CLIENT` cubre tanto "no hay segmento siguiente" como "segmento vacío" (barra final), igual que `clients.py`.

- [ ] **Step 9: Adaptar los consumidores (por ahora con `DEFAULT_CLIENT_ROOTS`)**

- **`lib/projects.ts`:**
  - la firma pasa a `projectsFor(sources, combined, source, client, roots: ClientRoot[])`;
  - la última línea usa `clientOf(path, roots)`;
  - importa `type ClientRoot` desde `@/lib/clients`.
- **`lib/projects.test.ts`:**
  - importa `DEFAULT_CLIENT_ROOTS` desde `@/lib/clients`;
  - añade `DEFAULT_CLIENT_ROOTS` como quinto argumento en cada llamada a `projectsFor`;
  - añade este caso:

  ```ts
  it("filtra por cliente con raíces propias", () => {
    const roots = [{ root: "/home/u/DEV/A", mode: "plano" as const }];
    expect(Object.keys(projectsFor(sources, combined, "all", "A", roots))).toEqual(["/home/u/DEV/A/x"]);
  });
  ```
- **`lib/commands.ts`:**
  - la firma pasa a `buildCommandEntries(sources, combined, roots: ClientRoot[])`;
  - `groupProjectsByClient(paths, roots)` y `clientOf(path, roots)` (dos veces).
- **`lib/commands.test.ts`:** `buildCommandEntries(sources, combined, DEFAULT_CLIENT_ROOTS)` y `buildCommandEntries(null, null, DEFAULT_CLIENT_ROOTS)`.
- **`components/CommandPalette.tsx`:** `buildCommandEntries(sources, combined, DEFAULT_CLIENT_ROOTS)`.
- **`App.tsx`:** `groupProjectsByClient(Object.keys(combined ?? {}), DEFAULT_CLIENT_ROOTS)`.
- **`components/TrendChart.tsx`:**
  - `buildSeries(data, section, clientFilter, roots: ClientRoot[])`, con `clientOf(row.project, roots)` dentro;
  - en el componente, `buildSeries(history.data, section, clientFilter, DEFAULT_CLIENT_ROOTS)`.
- **`components/SessionDetail.tsx`:** `clientOf(s.project, DEFAULT_CLIENT_ROOTS)`.
- **`components/RoiView.tsx`:** `groupProjectsByClient(allProjectPaths, DEFAULT_CLIENT_ROOTS)` y `clientOf(path, DEFAULT_CLIENT_ROOTS)`.
- **`views/ProjectsView.tsx`:** `projectsFor(..., DEFAULT_CLIENT_ROOTS)` en las líneas 38 y 53, y `groupProjectsByClient(Object.keys(all), DEFAULT_CLIENT_ROOTS)`.
- **`views/SpendView.tsx`:** `projectsFor(sources, combined, source, null, DEFAULT_CLIENT_ROOTS)`.

(La Task 6 sustituye cada `DEFAULT_CLIENT_ROOTS` de componentes por las raíces del contexto.)

- [ ] **Step 10: Verificación completa**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests && cd frontend && npx vitest run && npx oxlint && npx tsc -b --noEmit && npm run build`
Expected: todo en verde.

- [ ] **Step 11: Commit**

```bash
git add clients.py tests/test_clients.py tests/fixtures/client_of_cases.json briefing.py tests/test_briefing.py frontend/src
git commit -m "feat(clients): client_of con raíces configurables en backend y frontend"
```

---

### Task 2: Persistencia `app_settings` en `history.py`

**Files:**
- Modify: `history.py` (imports, `_SCHEMA`, funciones nuevas después de `save_roi_settings`)
- Create: `tests/test_app_settings.py`

**Interfaces:**
- Consumes: `clients.normalize_roots`, `clients.parse_stored_roots`, `clients.default_roots`, `clients.ClientRootsError` (Task 1).
- Produces:
  - `class AppSettingsError(ValueError)`
  - `get_app_settings(db_path=None) -> {"client_roots": list[dict], "onboarding_completed_at": str | None}`
  - `validate_app_settings(payload) -> {"client_roots": list[dict]}`: lanza `AppSettingsError`
  - `save_app_settings(settings, db_path=None) -> None`: recibe lo que devuelve `validate_app_settings`
  - `complete_onboarding(db_path=None, now=None) -> str`: devuelve la marca guardada

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_app_settings.py`:

```python
import os
import sqlite3
import tempfile
import unittest

import history

ROOTS = [{"root": "/srv/trabajo", "mode": "plano"}, {"root": "DEV", "mode": "cliente"}]


class AppSettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "history.db")


class TestGet(AppSettingsTestCase):
    def test_defaults_on_empty_db(self):
        self.assertEqual(history.get_app_settings(self.db),
                         {"client_roots": [{"root": "DEV", "mode": "cliente"}], "onboarding_completed_at": None})

    def test_old_db_without_table_gets_it_created(self):
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE daily_project (date TEXT, source TEXT, project TEXT, tokens INTEGER, cost REAL)")
        con.commit()
        con.close()
        self.assertIsNone(history.get_app_settings(self.db)["onboarding_completed_at"])

    def test_corrupt_values_fall_back_per_key(self):
        history.ensure_schema(self.db)
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO app_settings VALUES ('client_roots', '{roto', 'x')")
        con.execute("INSERT INTO app_settings VALUES ('onboarding_completed_at', '42', 'x')")
        con.commit()
        con.close()
        self.assertEqual(history.get_app_settings(self.db),
                         {"client_roots": [{"root": "DEV", "mode": "cliente"}], "onboarding_completed_at": None})


class TestSave(AppSettingsTestCase):
    def test_roundtrip_normalizes(self):
        clean = history.validate_app_settings({"client_roots": [{"root": "/srv/trabajo/", "mode": "plano"},
                                                                {"root": " DEV ", "mode": "cliente"}]})
        history.save_app_settings(clean, self.db)
        self.assertEqual(history.get_app_settings(self.db)["client_roots"], ROOTS)

    def test_validation_errors(self):
        for payload in ([1], {}, {"otra": 1}, {"client_roots": []},
                        {"client_roots": ROOTS, "onboarding_completed_at": "2026-01-01"}):
            with self.subTest(payload=payload), self.assertRaises(history.AppSettingsError):
                history.validate_app_settings(payload)

    def test_complete_onboarding_is_idempotent(self):
        first = history.complete_onboarding(self.db, now="2026-09-29T10:00:00+00:00")
        self.assertEqual(first, "2026-09-29T10:00:00+00:00")
        history.complete_onboarding(self.db, now="2026-09-30T10:00:00+00:00")
        self.assertEqual(history.get_app_settings(self.db)["onboarding_completed_at"], "2026-09-30T10:00:00+00:00")

    def test_complete_onboarding_default_now_is_utc_iso(self):
        stamp = history.complete_onboarding(self.db)
        self.assertTrue(stamp.endswith("+00:00"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest tests.test_app_settings -v`
Expected: FAIL con `AttributeError: module 'history' has no attribute 'get_app_settings'`.

- [ ] **Step 3: Implementar**

En `history.py`:
- añade `import json` a los imports de stdlib e `import clients` después de ellos;
- añade al final de `_SCHEMA`, antes del cierre `"""`:

```sql
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Después de `save_roi_settings`:

```python
# --- Ajustes de la aplicación (spec 2026-09-29 §3.1) ----------------------------

APP_SETTINGS_WRITABLE = ("client_roots",)


class AppSettingsError(ValueError):
    """Payload inválido para /api/app-settings; server.py lo traduce a HTTP 400."""


def get_app_settings(db_path=None):
    """Cada clave inválida o corrupta cae a su valor por defecto; nunca lanza por contenido."""
    db_path = db_path or DB_PATH_DEFAULT
    ensure_schema(db_path)
    con = sqlite3.connect(db_path)
    try:
        rows = dict(con.execute("SELECT key, value FROM app_settings").fetchall())
    finally:
        con.close()
    completed = None
    if rows.get("onboarding_completed_at") is not None:
        try:
            value = json.loads(rows["onboarding_completed_at"])
        except ValueError:
            value = None
        completed = value if isinstance(value, str) and value else None
    return {"client_roots": clients.parse_stored_roots(rows.get("client_roots")),
            "onboarding_completed_at": completed}


def validate_app_settings(payload):
    if not isinstance(payload, dict):
        raise AppSettingsError("El cuerpo debe ser un objeto JSON")
    unknown = sorted(set(payload) - set(APP_SETTINGS_WRITABLE))
    if unknown:
        raise AppSettingsError(f"Clave desconocida: {unknown[0]}")
    if "client_roots" not in payload:
        raise AppSettingsError("Falta client_roots")
    try:
        return {"client_roots": clients.normalize_roots(payload["client_roots"])}
    except clients.ClientRootsError as exc:
        raise AppSettingsError(str(exc)) from exc


def _put_app_setting(db_path, key, value):
    db_path = db_path or DB_PATH_DEFAULT
    ensure_schema(db_path)
    con = sqlite3.connect(db_path)
    try:
        with con:
            con.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                        (key, json.dumps(value, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
    finally:
        con.close()


def save_app_settings(settings, db_path=None):
    """Recibe el resultado de validate_app_settings."""
    _put_app_setting(db_path, "client_roots", settings["client_roots"])


def complete_onboarding(db_path=None, now=None):
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    _put_app_setting(db_path, "onboarding_completed_at", now)
    return now
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests`
Expected: todo OK.

- [ ] **Step 5: Commit**

```bash
git add history.py tests/test_app_settings.py
git commit -m "feat(history): tabla app_settings con raíces de cliente y marca de onboarding"
```

---

### Task 3: Briefing con raíces configuradas (solo lectura)

**Files:**
- Modify: `briefing.py` (`client_of`, `top_projects`, `rule_project_concentration`, `build_context`, `build_briefing`, `load`, `get_briefing`)
- Modify: `tests/test_briefing.py`

**Interfaces:**
- Consumes: `clients.client_of`, `clients.parse_stored_roots`, `clients.default_roots` (Task 1); la tabla `app_settings` (Task 2).
- Produces:
  - `briefing.load_client_roots(db_path) -> list[dict]`: solo lectura. Si no hay archivo, tabla o clave, devuelve las raíces por defecto. Los `sqlite3.Error` se propagan.
  - `build_context(..., source="all", roots=None)`, que añade `ctx["roots"]`.
  - `build_briefing(..., degraded=False, roots=None)`.
  - `top_projects(rows, roots, limit=3)`.
- `briefing.load` **no cambia** su tupla de 3 elementos, porque `recommend/engine.py:173` la desempaqueta. `recommend/cost.py` sigue llamando a `build_context` sin `roots`, es decir, con las raíces por defecto. Es deliberado: de ese link el motor solo usa el proyecto (`project_from_link`), no el cliente.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_briefing.py`, añade `import clients` junto a `import briefing` y estas clases al final (antes de `if __name__`, si existe):

```python
class TestClientRoots(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "history.db")

    def test_top_projects_and_concentration_link_use_given_roots(self):
        roots = [{"root": "/srv/trabajo", "mode": "plano"}]
        rows = [row("2026-09-02", project="/srv/trabajo/api", cost=90), row("2026-09-02", project="/tmp/x", cost=10)]
        data = briefing.build_briefing(rows, [], NO_SETTINGS, TODAY, roots=roots)
        self.assertEqual(data["top_projects"][0]["client"], "trabajo")
        link = next(s["link"] for s in data["attention"] if s["id"] == "project_concentration")
        self.assertTrue(link.startswith("/proyectos/trabajo?"))

    def test_default_roots_when_not_given(self):
        data = build([row("2026-09-02", project="/home/u/DEV/ACME/app")])
        self.assertEqual(data["top_projects"][0]["client"], "ACME")

    def test_load_client_roots_without_db_does_not_create_it(self):
        self.assertEqual(briefing.load_client_roots(self.db), clients.default_roots())
        self.assertFalse(os.path.exists(self.db))

    def test_load_client_roots_old_db_without_table(self):
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE daily_project (date TEXT, source TEXT, project TEXT, tokens INTEGER, cost REAL)")
        con.commit()
        con.close()
        self.assertEqual(briefing.load_client_roots(self.db), clients.default_roots())

    def test_load_client_roots_reads_saved_value(self):
        roots = [{"root": "work", "mode": "cliente"}]
        history.save_app_settings({"client_roots": roots}, self.db)
        self.assertEqual(briefing.load_client_roots(self.db), roots)

    def test_get_briefing_uses_saved_roots(self):
        history.save_app_settings({"client_roots": [{"root": "work", "mode": "cliente"}]}, self.db)
        history.record_snapshot(
            {"claude_code": {"/home/u/work/Initech/api": {"by_day": {"2026-09-02": {"tokens": 10, "cost": 5.0}}}},
             "codex": {}, "opencode": {}, "hermes": {}, "openrouter": {"unavailable": True}},
            db_path=self.db)
        data = briefing.get_briefing(db_path=self.db, today=TODAY)
        self.assertEqual(data["top_projects"][0]["client"], "Initech")
```

(`history.record_snapshot(sources, db_path)` recorre `by_day` de las cuatro fuentes por proyecto con claves `tokens`/`cost`; es la forma exacta de `history.py:84`.)

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest tests.test_briefing -v`
Expected: FAIL (`build_briefing() got an unexpected keyword argument 'roots'`, `load_client_roots` no existe).

- [ ] **Step 3: Implementar**

En `briefing.py`:

```python
def client_of(path, roots=None):
    """Cliente del proyecto según las raíces configuradas (clients.client_of)."""
    return clients.client_of(path, roots if roots is not None else clients.default_roots())


def top_projects(rows, roots, limit=3):
    costs = _project_costs(rows)
    total = sum(costs.values())
    ranked = sorted(costs.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"project": p, "client": client_of(p, roots), "cost": round(c, 2),
             "share": round(c / total, 3) if total > 0 else 0.0} for p, c in ranked]
```

En `rule_project_concentration`, el link pasa a usar `client_of(project, ctx.get("roots"))`.

`build_context`:

```python
def build_context(project_rows, model_rows, settings, today, source="all", roots=None):
    """Contexto que consumen las RULES: lo usan el briefing y el motor de
    recomendaciones (recommend/cost.py), que lo evalúa por fuente."""
    rows = rows_for_source(source, project_rows, model_rows)
    window = month_window(month_of(today), today.day)
    return {"source": source, "today": today, "window": window, "rows": rows,
            "window_rows": in_range(rows, *window), "project_rows": project_rows,
            "model_rows": model_rows, "settings": settings,
            "roots": roots if roots is not None else clients.default_roots()}
```

`build_briefing`:
- la firma pasa a `def build_briefing(project_rows, model_rows, settings, today, source="all", compare=None, degraded=False, roots=None):`;
- llama a `build_context(project_rows, model_rows, settings, today, source, roots)`;
- usa `"top_projects": top_projects(window_rows, ctx["roots"]),`.

Nueva función después de `load`:

```python
def load_client_roots(db_path):
    """Raíces de cliente en solo lectura. Sin archivo, tabla o clave → por defecto.
    Los sqlite3.Error se propagan para que get_briefing los marque como degradados."""
    if not os.path.exists(db_path):
        return clients.default_roots()
    con = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "app_settings" not in tables:
            return clients.default_roots()
        row = con.execute("SELECT value FROM app_settings WHERE key = 'client_roots'").fetchone()
    finally:
        con.close()
    return clients.parse_stored_roots(row[0] if row else None)
```

`get_briefing`:

```python
    try:
        project_rows, model_rows, settings = load(db_path)
        roots = load_client_roots(db_path)
        degraded = False
    except sqlite3.Error as exc:
        log.warning("briefing: no se pudo leer %s: %s", db_path, exc)
        project_rows, model_rows, settings = [], [], _empty_settings()
        roots = clients.default_roots()
        degraded = True
    return build_briefing(project_rows, model_rows, settings, today,
                          source=source, compare=compare, degraded=degraded, roots=roots)
```

- [ ] **Step 4: Ejecutar la suite completa**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests`
Expected: todo OK, incluidos `test_recommend_cost` y `test_recommend_engine` sin cambios.

- [ ] **Step 5: Commit**

```bash
git add briefing.py tests/test_briefing.py
git commit -m "feat(briefing): agrupar por las raíces de cliente guardadas (solo lectura)"
```

---

### Task 4: API `/api/app-settings` y `available` en `/api/engine-settings`

**Files:**
- Modify: `server.py` (imports, `do_GET`, `do_POST`)
- Modify: `tests/test_server_recommendations.py`

**Interfaces:**
- Consumes: `history.get_app_settings`, `validate_app_settings`, `save_app_settings`, `complete_onboarding`, `AppSettingsError` (Task 2); `clients.default_roots` (Task 1).
- Produces (HTTP):
  - `GET /api/app-settings` → `200 {"client_roots": [...], "onboarding_completed_at": str|null, "degraded": bool}`.
  - `POST /api/app-settings`: cuerpo `{"client_roots": [...]}`. Responde `200` con la misma forma que el GET; `400 {"error"}` si la validación falla; `415` si el cuerpo no es JSON; `503 {"error"}` ante un `sqlite3.Error`.
  - `POST /api/app-settings/onboarding`: cuerpo `{}`. Responde `200 {"onboarding_completed_at": str}`; `415` si no es JSON; `503` ante un `sqlite3.Error`.
  - `GET /api/engine-settings` añade `"available": {"hermes": bool, "claude": bool}`. El `POST` no cambia.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_server_recommendations.py`, reemplaza la línea `self.assertEqual(self.request("GET", "/api/engine-settings"), (200, payload))` de `test_roundtrip_and_validation` por:

```python
        status, body = self.request("GET", "/api/engine-settings")
        self.assertEqual(status, 200)
        self.assertEqual({k: body[k] for k in payload}, payload)
        self.assertEqual(set(body["available"]), {"hermes", "claude"})
```

Añade a `TestEngineSettings`:

```python
    def test_available_reflects_path(self):
        with patch("server.shutil.which", side_effect=lambda name: "/x/hermes" if name == "hermes" else None):
            body = self.request("GET", "/api/engine-settings")[1]
        self.assertEqual(body["available"], {"hermes": True, "claude": False})
```

Y una clase nueva antes de `TestCheckRecommendationRuns`:

```python
class TestAppSettings(RecommendationsAPITestCase):
    ROOTS = [{"root": "/srv/trabajo", "mode": "plano"}]

    def test_defaults_then_roundtrip(self):
        self.assertEqual(self.request("GET", "/api/app-settings"), (200, {
            "client_roots": [{"root": "DEV", "mode": "cliente"}], "onboarding_completed_at": None, "degraded": False}))
        status, body = self.request("POST", "/api/app-settings", {"client_roots": [{"root": "/srv/trabajo/", "mode": "plano"}]})
        self.assertEqual((status, body["client_roots"]), (200, self.ROOTS))
        self.assertEqual(self.request("GET", "/api/app-settings")[1]["client_roots"], self.ROOTS)

    def test_validation_and_content_type(self):
        status, body = self.request("POST", "/api/app-settings", {"client_roots": []})
        self.assertEqual(status, 400)
        self.assertIn("entre 1 y 20", body["error"])
        self.assertEqual(self.request("POST", "/api/app-settings", {"otra": 1})[0], 400)
        self.assertEqual(self.request("POST", "/api/app-settings", {"client_roots": self.ROOTS}, "text/plain")[0], 415)

    def test_complete_onboarding(self):
        status, body = self.request("POST", "/api/app-settings/onboarding", {})
        self.assertEqual(status, 200)
        stamp = body["onboarding_completed_at"]
        self.assertTrue(stamp)
        self.assertEqual(self.request("GET", "/api/app-settings")[1]["onboarding_completed_at"], stamp)
        self.assertEqual(self.request("POST", "/api/app-settings/onboarding", b"", "text/plain")[0], 415)

    def test_sqlite_error_is_degraded_not_500(self):
        with patch("server.history.get_app_settings", side_effect=sqlite3.OperationalError("disk I/O")):
            status, body = self.request("GET", "/api/app-settings")
        self.assertEqual((status, body["degraded"], body["onboarding_completed_at"]), (200, True, None))
        with patch("server.history.save_app_settings", side_effect=sqlite3.OperationalError("disk I/O")):
            self.assertEqual(self.request("POST", "/api/app-settings", {"client_roots": self.ROOTS})[0], 503)
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest tests.test_server_recommendations -v`
Expected: FAIL (404 en `/api/app-settings`, `KeyError: 'available'`).

- [ ] **Step 3: Implementar**

En `server.py`, añade `import shutil` a los imports de stdlib e `import clients` junto a `import briefing`. Después de `_state = ...` añade:

```python
AVAILABLE_BACKENDS = ("hermes", "claude")


def _available_backends():
    """Se evalúa en cada request: refleja una instalación hecha sin reiniciar el server."""
    return {name: shutil.which(name) is not None for name in AVAILABLE_BACKENDS}


def _app_settings_payload(db_path):
    try:
        return {**history.get_app_settings(db_path=db_path), "degraded": False}
    except sqlite3.Error:
        return {"client_roots": clients.default_roots(), "onboarding_completed_at": None, "degraded": True}
```

En `do_GET`, antes de `elif parsed.path == "/api/recommendations":`:

```python
            elif parsed.path == "/api/app-settings":
                self._send_json(json.dumps(_app_settings_payload(db_path)))
```

En la rama `GET /api/engine-settings`, después del `try/except` y antes de `_send_json`:

```python
                data["available"] = _available_backends()
```

En `do_POST`, después de la rama `/api/roi-settings`:

```python
            elif parsed.path == "/api/app-settings":
                body = self._read_json_body()
                if body is _INVALID:
                    return
                try:
                    clean = history.validate_app_settings(body)
                except history.AppSettingsError as exc:
                    self._send_json(json.dumps({"error": str(exc)}), status=400)
                    return
                try:
                    history.save_app_settings(clean, db_path=db_path)
                except sqlite3.Error as exc:
                    self._send_json(json.dumps({"error": f"Base no disponible: {exc}"}), status=503)
                    return
                self._send_json(json.dumps(_app_settings_payload(db_path)))
            elif parsed.path == "/api/app-settings/onboarding":
                if self._read_json_body() is _INVALID:
                    return
                try:
                    stamp = history.complete_onboarding(db_path=db_path)
                except sqlite3.Error as exc:
                    self._send_json(json.dumps({"error": f"Base no disponible: {exc}"}), status=503)
                    return
                self._send_json(json.dumps({"onboarding_completed_at": stamp}))
```

- [ ] **Step 4: Ejecutar la suite completa**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests`
Expected: todo OK.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server_recommendations.py
git commit -m "feat(server): /api/app-settings, onboarding y backends disponibles"
```

---

### Task 5: Lógica pura del frontend: api, rutas y onboarding

**Files:**
- Modify: `frontend/src/lib/api.ts`, `frontend/src/lib/routes.ts`, `frontend/src/lib/routes.test.ts`
- Create: `frontend/src/lib/onboarding.ts`, `frontend/src/lib/onboarding.test.ts`

**Interfaces:**
- Consumes: `ClientRoot` y `DEFAULT_CLIENT_ROOTS` (Task 1); los endpoints de la Task 4.
- Produces (`lib/api.ts`):
  - `interface AppSettings { client_roots: ClientRoot[]; onboarding_completed_at: string | null; degraded: boolean }`
  - `fetchAppSettings(): Promise<AppSettings>`
  - `saveAppSettings(s: { client_roots: ClientRoot[] }): Promise<AppSettings>`
  - `completeOnboarding(): Promise<{ onboarding_completed_at: string }>`
  - `interface AvailableBackends { hermes: boolean; claude: boolean }`
  - `interface EngineSettingsResponse extends EngineSettings { available: AvailableBackends }`
  - `fetchEngineSettings(): Promise<EngineSettingsResponse>`
  - `errorDetail(err: unknown): string | null`: el mensaje del servidor en un 400 y `null` en cualquier otro caso
- Produces (`lib/routes.ts`): `ViewKey` incluye `"onboarding"`; `parsePath("/bienvenida")` → `{ view: "onboarding", client: null }`; `viewPath("onboarding")` → `"/bienvenida"`.
- Produces (`lib/onboarding.ts`):
  - `interface OnboardingGate { loading: boolean; error: string | null; degraded: boolean; completedAt: string | null }`
  - `shouldRedirectToOnboarding(gate: OnboardingGate, pathname: string): boolean`
  - `suggestRoots(paths: string[]): ClientRoot[]`
  - `suggestBackend(available: AvailableBackends): EngineBackend`
  - `type OnboardingStep = "folders" | "roi" | "engine"`, `ONBOARDING_STEPS: OnboardingStep[]`
  - `interface OnboardingDraft { roots: ClientRoot[]; roi: Partial<RoiSettings> | null; engine: EngineSettings }` (`roi: null` significa "no tocar ROI")
  - `interface OnboardingApi { saveAppSettings; saveRoiSettings; saveEngineSettings; completeOnboarding }`, con las firmas de `lib/api.ts`
  - `type SaveResult = { ok: true } | { ok: false; step: OnboardingStep; message: string }`
  - `saveOnboarding(draft: OnboardingDraft, api: OnboardingApi): Promise<SaveResult>`
  - `skipDraft(available: AvailableBackends, llmChain: string[]): OnboardingDraft`

- [ ] **Step 1: Escribir los tests que fallan**

En `frontend/src/lib/routes.test.ts`, dentro de `it("vistas nuevas", ...)`, añade:

```ts
    expect(parsePath("/bienvenida")).toEqual({ view: "onboarding", client: null });
```

y dentro de `it("rutas desconocidas o mal codificadas → null", ...)`:

```ts
    expect(parsePath("/bienvenida/otra")).toBeNull();
```

`frontend/src/lib/onboarding.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { HttpError } from "@/lib/api";
import {
  saveOnboarding, shouldRedirectToOnboarding, skipDraft, suggestBackend, suggestRoots, type OnboardingDraft,
} from "@/lib/onboarding";

const ready = { loading: false, error: null, degraded: false, completedAt: null };

describe("shouldRedirectToOnboarding", () => {
  it("redirige solo con ajustes cargados, sin error y sin completar", () => {
    expect(shouldRedirectToOnboarding(ready, "/")).toBe(true);
    expect(shouldRedirectToOnboarding(ready, "/gasto/roi")).toBe(true);
    expect(shouldRedirectToOnboarding(ready, "/bienvenida")).toBe(false);
    expect(shouldRedirectToOnboarding({ ...ready, completedAt: "2026-09-29T10:00:00+00:00" }, "/")).toBe(false);
  });
  it("nunca atrapa al usuario si no se pudo leer el estado", () => {
    expect(shouldRedirectToOnboarding({ ...ready, loading: true }, "/")).toBe(false);
    expect(shouldRedirectToOnboarding({ ...ready, error: "HTTP 404" }, "/")).toBe(false);
    expect(shouldRedirectToOnboarding({ ...ready, degraded: true }, "/")).toBe(false);
  });
});

describe("suggestRoots", () => {
  it("propone la carpeta común dos niveles arriba, sin duplicar por mayúsculas", () => {
    expect(suggestRoots(["/home/u/DEV/ACME/app", "/home/u/DEV/BETA/api", "/home/u/dev/GAMMA/x"])).toEqual([
      { root: "DEV", mode: "cliente" },
    ]);
  });
  it("ordena por frecuencia y limita a tres", () => {
    const paths = ["/srv/work/A/x", "/srv/work/B/y", "/srv/work/C/z", "/opt/src/D/q", "/opt/src/E/r"];
    expect(suggestRoots(paths)).toEqual([{ root: "work", mode: "cliente" }, { root: "src", mode: "cliente" }]);
  });
  it("descarta home, Users y el nombre de usuario", () => {
    expect(suggestRoots(["/home/u/app", "/home/u/api", "/Users/ana/code/x", "/Users/ana/code/y"])).toEqual([
      { root: "DEV", mode: "cliente" },
    ]);
  });
  it("sin proyectos o con uno solo por carpeta → valor por defecto", () => {
    expect(suggestRoots([])).toEqual([{ root: "DEV", mode: "cliente" }]);
    expect(suggestRoots(["/srv/work/A/x"])).toEqual([{ root: "DEV", mode: "cliente" }]);
  });
});

describe("suggestBackend", () => {
  it("hermes → claude → none", () => {
    expect(suggestBackend({ hermes: true, claude: true })).toBe("hermes");
    expect(suggestBackend({ hermes: false, claude: true })).toBe("claude");
    expect(suggestBackend({ hermes: false, claude: false })).toBe("none");
  });
});

describe("saveOnboarding", () => {
  const draft: OnboardingDraft = {
    roots: [{ root: "DEV", mode: "cliente" }],
    roi: { hourly_rate: 30 },
    engine: { backend: "none", llm_chain: ["nous:x:free"] },
  };
  const fakeApi = () => ({
    saveAppSettings: vi.fn().mockResolvedValue({}),
    saveRoiSettings: vi.fn().mockResolvedValue({}),
    saveEngineSettings: vi.fn().mockResolvedValue({}),
    completeOnboarding: vi.fn().mockResolvedValue({ onboarding_completed_at: "t" }),
  });

  it("guarda en orden y marca el onboarding al final", async () => {
    const api = fakeApi();
    const calls: string[] = [];
    for (const [name, fn] of Object.entries(api)) fn.mockImplementation(async () => { calls.push(name); return {}; });
    expect(await saveOnboarding(draft, api)).toEqual({ ok: true });
    expect(calls).toEqual(["saveAppSettings", "saveRoiSettings", "saveEngineSettings", "completeOnboarding"]);
    expect(api.saveAppSettings).toHaveBeenCalledWith({ client_roots: draft.roots });
  });

  it("roi null no toca ROI", async () => {
    const api = fakeApi();
    await saveOnboarding({ ...draft, roi: null }, api);
    expect(api.saveRoiSettings).not.toHaveBeenCalled();
  });

  it("un fallo detiene el guardado, no marca el onboarding e indica el paso", async () => {
    const api = fakeApi();
    api.saveRoiSettings.mockRejectedValue(new HttpError("POST /api/roi-settings → HTTP 400: hourly_rate debe ser numérico o null", 400));
    expect(await saveOnboarding(draft, api)).toEqual({ ok: false, step: "roi", message: "hourly_rate debe ser numérico o null" });
    expect(api.saveEngineSettings).not.toHaveBeenCalled();
    expect(api.completeOnboarding).not.toHaveBeenCalled();
  });

  it("un error de red usa un mensaje genérico", async () => {
    const api = fakeApi();
    api.completeOnboarding.mockRejectedValue(new TypeError("Failed to fetch"));
    expect(await saveOnboarding(draft, api)).toEqual({
      ok: false, step: "engine", message: "No se pudo guardar. Revisa que el servidor siga activo e inténtalo de nuevo.",
    });
  });
});

describe("skipDraft", () => {
  it("raíces por defecto, backend sugerido, sin ROI", () => {
    expect(skipDraft({ hermes: false, claude: true }, ["a:b:free"])).toEqual({
      roots: [{ root: "DEV", mode: "cliente" }], roi: null, engine: { backend: "claude", llm_chain: ["a:b:free"] },
    });
  });
});
```

Run: `cd frontend && npx vitest run src/lib/onboarding.test.ts src/lib/routes.test.ts`
Expected: FAIL (el módulo `@/lib/onboarding` no existe y `parsePath("/bienvenida")` es null).

- [ ] **Step 2: Implementar `lib/api.ts`**

Añade `import type { ClientRoot } from "@/lib/clients";` arriba. Después de `saveRoiSettings`:

```ts
export interface AppSettings {
  client_roots: ClientRoot[];
  onboarding_completed_at: string | null;
  degraded: boolean;
}

export function fetchAppSettings(): Promise<AppSettings> {
  return getJson("/api/app-settings");
}

export function saveAppSettings(settings: { client_roots: ClientRoot[] }): Promise<AppSettings> {
  return getJson("/api/app-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export function completeOnboarding(): Promise<{ onboarding_completed_at: string }> {
  return getJson("/api/app-settings/onboarding", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
}

/** Mensaje del servidor en un 400 ("… → HTTP 400: <mensaje>"); null en cualquier otro caso. */
export function errorDetail(err: unknown): string | null {
  if (!(err instanceof HttpError) || err.status !== 400) return null;
  const detail = err.message.split(": ").slice(1).join(": ");
  return detail || null;
}
```

Junto a `EngineSettings`:

```ts
export interface AvailableBackends {
  hermes: boolean;
  claude: boolean;
}

export interface EngineSettingsResponse extends EngineSettings {
  available: AvailableBackends;
}
```

Cambia `fetchEngineSettings` a `Promise<EngineSettingsResponse>`. En `EngineSettingsForm.tsx`, reemplaza la expresión de `setSaveError(...)` por `setSaveError(errorDetail(err))` e importa `errorDetail`. Quita `HttpError` de ese import si queda sin uso.

- [ ] **Step 3: Implementar la ruta `/bienvenida`**

En `lib/routes.ts`:
- `VIEW_KEYS` pasa a `["home", "activity", "spend", "roi", "projects", "recommendations", "settings", "onboarding"]`;
- `VIEW_PATH` añade `onboarding: "/bienvenida",`;
- en `parsePath`, antes de `return null;`, añade `if (head === "bienvenida" && rest.length === 0) return { view: "onboarding", client: null };`;
- en el comentario de cabecera, añade la línea `/bienvenida → configuración inicial (fuera del layout con sidebar)`.

`lib/commands.ts` y `Sidebar.tsx` usan listas explícitas de vistas, así que no se tocan.

- [ ] **Step 4: Implementar `lib/onboarding.ts`**

```ts
import {
  errorDetail, type AppSettings, type AvailableBackends, type EngineBackend, type EngineSettings, type RoiSettings,
} from "@/lib/api";
import { DEFAULT_CLIENT_ROOTS, type ClientRoot } from "@/lib/clients";
import { parsePath } from "@/lib/routes";

export interface OnboardingGate {
  loading: boolean;
  error: string | null;
  degraded: boolean;
  completedAt: string | null;
}

/** Solo redirige si el servidor confirmó que falta el onboarding: un error nunca atrapa al usuario. */
export function shouldRedirectToOnboarding(gate: OnboardingGate, pathname: string): boolean {
  if (gate.loading || gate.error || gate.degraded || gate.completedAt !== null) return false;
  return parsePath(pathname)?.view !== "onboarding";
}

const MAX_SUGGESTED = 3;
const HOME_DIRS = new Set(["home", "users"]);

/** Carpeta dos niveles arriba de cada proyecto (/x/DEV/ACME/app → DEV) repetida en ≥2 proyectos. */
export function suggestRoots(paths: string[]): ClientRoot[] {
  const counts = new Map<string, { name: string; count: number }>();
  for (const path of paths) {
    const segments = path.split("/");
    const idx = segments.length - 3;
    if (idx < 1) continue;
    const name = segments[idx];
    if (!name || HOME_DIRS.has(name.toLowerCase()) || HOME_DIRS.has(segments[idx - 1].toLowerCase())) continue;
    const key = name.toUpperCase();
    const entry = counts.get(key) ?? { name, count: 0 };
    entry.count += 1;
    counts.set(key, entry);
  }
  const ranked = [...counts.values()]
    .filter((e) => e.count >= 2)
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
    .slice(0, MAX_SUGGESTED);
  return ranked.length > 0
    ? ranked.map((e) => ({ root: e.name, mode: "cliente" as const }))
    : DEFAULT_CLIENT_ROOTS.map((r) => ({ ...r }));
}

export function suggestBackend(available: AvailableBackends): EngineBackend {
  if (available.hermes) return "hermes";
  if (available.claude) return "claude";
  return "none";
}

export type OnboardingStep = "folders" | "roi" | "engine";
export const ONBOARDING_STEPS: OnboardingStep[] = ["folders", "roi", "engine"];

export interface OnboardingDraft {
  roots: ClientRoot[];
  /** null = no tocar los ajustes de ROI (Omitir). */
  roi: Partial<RoiSettings> | null;
  engine: EngineSettings;
}

export interface OnboardingApi {
  saveAppSettings: (s: { client_roots: ClientRoot[] }) => Promise<AppSettings | unknown>;
  saveRoiSettings: (s: Partial<RoiSettings>) => Promise<unknown>;
  saveEngineSettings: (s: EngineSettings) => Promise<unknown>;
  completeOnboarding: () => Promise<unknown>;
}

export type SaveResult = { ok: true } | { ok: false; step: OnboardingStep; message: string };

const GENERIC_ERROR = "No se pudo guardar. Revisa que el servidor siga activo e inténtalo de nuevo.";

/** Guarda en orden y marca el onboarding al final. Cada guardado es idempotente: reintentar es seguro. */
export async function saveOnboarding(draft: OnboardingDraft, api: OnboardingApi): Promise<SaveResult> {
  const steps: [OnboardingStep, () => Promise<unknown>][] = [
    ["folders", () => api.saveAppSettings({ client_roots: draft.roots })],
    ...(draft.roi ? [["roi", () => api.saveRoiSettings(draft.roi as Partial<RoiSettings>)] as [OnboardingStep, () => Promise<unknown>]] : []),
    ["engine", () => api.saveEngineSettings(draft.engine)],
    ["engine", () => api.completeOnboarding()],
  ];
  for (const [step, run] of steps) {
    try {
      await run();
    } catch (err) {
      return { ok: false, step, message: errorDetail(err) ?? GENERIC_ERROR };
    }
  }
  return { ok: true };
}

export function skipDraft(available: AvailableBackends, llmChain: string[]): OnboardingDraft {
  return {
    roots: DEFAULT_CLIENT_ROOTS.map((r) => ({ ...r })),
    roi: null,
    engine: { backend: suggestBackend(available), llm_chain: llmChain },
  };
}
```

- [ ] **Step 5: Verificación del frontend**

Run: `cd frontend && npx vitest run && npx oxlint && npx tsc -b --noEmit && npm run build`
Expected: todo en verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): api de ajustes, ruta /bienvenida y lógica pura del onboarding"
```

---

### Task 6: Contexto de ajustes y raíces reales en todos los consumidores

**Files:**
- Create: `frontend/src/hooks/appSettingsContext.ts`, `frontend/src/components/AppSettingsProvider.tsx`
- Modify: `frontend/src/main.tsx`, `frontend/src/App.tsx`
- Modify: `components/TrendChart.tsx`, `SessionDetail.tsx`, `RoiView.tsx`, `CommandPalette.tsx`
- Modify: `views/ProjectsView.tsx`, `SpendView.tsx`

**Interfaces:**
- Consumes: `fetchAppSettings` (Task 5); `DEFAULT_CLIENT_ROOTS` y `ClientRoot` (Task 1).
- Produces:
  - `interface AppSettingsState { roots: ClientRoot[]; completedAt: string | null; loading: boolean; error: string | null; degraded: boolean; reload: () => Promise<void> }`
  - `AppSettingsContext`
  - `useAppSettings(): AppSettingsState`
  - `useClientRoots(): ClientRoot[]`
  - `<AppSettingsProvider>`

Esta tarea no tiene lógica pura nueva: su verificación es `tsc` más la suite de vitest existente. La interacción queda para el E2E.

- [ ] **Step 1: Crear el contexto**

`frontend/src/hooks/appSettingsContext.ts`:

```ts
import { createContext, useContext } from "react";
import { DEFAULT_CLIENT_ROOTS, type ClientRoot } from "@/lib/clients";

export interface AppSettingsState {
  roots: ClientRoot[];
  completedAt: string | null;
  loading: boolean;
  error: string | null;
  degraded: boolean;
  reload: () => Promise<void>;
}

const FALLBACK: AppSettingsState = {
  roots: DEFAULT_CLIENT_ROOTS,
  completedAt: null,
  loading: false,
  error: "AppSettingsProvider ausente",
  degraded: false,
  reload: async () => {},
};

export const AppSettingsContext = createContext<AppSettingsState>(FALLBACK);

export function useAppSettings(): AppSettingsState {
  return useContext(AppSettingsContext);
}

export function useClientRoots(): ClientRoot[] {
  return useContext(AppSettingsContext).roots;
}
```

(`FALLBACK` lleva `error`, así que sin provider nunca se redirige al onboarding.)

- [ ] **Step 2: Crear el provider**

`frontend/src/components/AppSettingsProvider.tsx`:

```tsx
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AppSettingsContext, type AppSettingsState } from "@/hooks/appSettingsContext";
import { fetchAppSettings } from "@/lib/api";
import { DEFAULT_CLIENT_ROOTS } from "@/lib/clients";

type Loaded = Omit<AppSettingsState, "reload">;

/** Carga /api/app-settings una vez. Si falla, raíces por defecto y sin redirigir al onboarding. */
export function AppSettingsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Loaded>({
    roots: DEFAULT_CLIENT_ROOTS, completedAt: null, loading: true, error: null, degraded: false,
  });

  const reload = useCallback(async () => {
    try {
      const s = await fetchAppSettings();
      setState({ roots: s.client_roots, completedAt: s.onboarding_completed_at, loading: false, error: null, degraded: s.degraded });
    } catch (err) {
      setState((prev) => ({ ...prev, loading: false, error: (err as Error).message }));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const value = useMemo(() => ({ ...state, reload }), [state, reload]);
  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}
```

- [ ] **Step 3: Montar el provider**

En `main.tsx`, importa `AppSettingsProvider` y envuelve:

```tsx
    <BrowserRouter>
      <AppSettingsProvider>
        <App />
      </AppSettingsProvider>
    </BrowserRouter>
```

- [ ] **Step 4: Sustituir `DEFAULT_CLIENT_ROOTS` por `useClientRoots()` en los componentes**

En cada componente, llama al hook al principio del cuerpo, antes de cualquier `return` temprano, y pasa `roots` donde en la Task 1 iba `DEFAULT_CLIENT_ROOTS`:

- **`App.tsx`:** `const roots = useClientRoots();` junto a los demás hooks, y `groupProjectsByClient(Object.keys(combined ?? {}), roots)`.
- **`CommandPalette.tsx`:** `const roots = useClientRoots();` y `useMemo(() => buildCommandEntries(sources, combined, roots), [sources, combined, roots])`.
- **`TrendChart.tsx`:** `const roots = useClientRoots();` y `buildSeries(history.data, section, clientFilter, roots)`.
- **`SessionDetail.tsx`:**
  - `const roots = useClientRoots();` va **antes** del `if (section === "openrouter") return null;`, por la regla de hooks;
  - `clientOf(s.project, roots)`.
- **`RoiView.tsx`:** `const roots = useClientRoots();` junto a sus otros hooks, en `groupProjectsByClient` y `clientOf`.
- **`ProjectsView.tsx`:** `const roots = useClientRoots();` al inicio, en ambas llamadas a `projectsFor` y en `groupProjectsByClient`.
- **`SpendView.tsx`:** `const roots = useClientRoots();` y `projectsFor(sources, combined, source, null, roots)`.

Quita los imports de `DEFAULT_CLIENT_ROOTS` que queden sin uso.

Run: `cd frontend && grep -rn "DEFAULT_CLIENT_ROOTS" src --include=*.tsx`
Expected: sin resultados (`DEFAULT_CLIENT_ROOTS` solo se usa desde `lib/`, `hooks/` y `AppSettingsProvider`). Si aparece `AppSettingsProvider.tsx`, es correcto.

- [ ] **Step 5: Verificación del frontend**

Run: `cd frontend && npx vitest run && npx oxlint && npx tsc -b --noEmit && npm run build`
Expected: todo en verde. Si oxlint marca `react-refresh/only-export-components` en algún archivo, la separación en `hooks/appSettingsContext.ts` y `components/AppSettingsProvider.tsx` ya lo evita. No mezcles los dos.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): contexto de ajustes y raíces configuradas en todas las vistas"
```

---

### Task 7: Configuración: raíces de cliente, ROI reutilizable y repetir onboarding

**Files:**
- Create: `frontend/src/lib/roiDraft.ts`, `frontend/src/lib/roiDraft.test.ts`
- Create: `frontend/src/components/RoiFields.tsx`, `ClientRootsEditor.tsx`, `ClientRootsForm.tsx`
- Modify: `frontend/src/components/SettingsForm.tsx`, `frontend/src/views/SettingsView.tsx`
- Modify: `frontend/src/lib/settings.ts`, `frontend/src/lib/settings.test.ts`

**Interfaces:**
- Consumes: `previewClients`, `MAX_CLIENT_ROOTS`, `ClientRoot` (Task 1); `saveAppSettings`, `errorDetail` (Task 5); `useAppSettings` (Task 6); `SourceStatus` (`lib/settings.ts`).
- Produces:
  - `type RoiDraft = Record<keyof RoiSettings, string>`
  - `toRoiDraft(s: RoiSettings): RoiDraft`
  - `roiPayload(d: RoiDraft): Partial<RoiSettings>`
  - `type RoiPlan = "claude" | "codex"`
  - `plansWithData(statuses: SourceStatus[]): RoiPlan[]`
  - `projectPaths(sources: UsageSnapshot["sources"] | null): string[]`, en `lib/settings.ts`
  - `<RoiFields draft onChange plans?>`
  - `<ClientRootsEditor roots onChange paths>`
  - `<ClientRootsForm paths>`

- [ ] **Step 1: Escribir los tests que fallan**

`frontend/src/lib/roiDraft.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { plansWithData, roiPayload, toRoiDraft } from "@/lib/roiDraft";
import type { SourceStatus } from "@/lib/settings";

describe("roiDraft", () => {
  it("ida y vuelta: vacíos → null, números → number", () => {
    const draft = toRoiDraft({
      subscription_cost_claude: 20, subscription_cost_codex: null, hourly_rate: 35,
      subscription_start_claude: "2026-07-18", subscription_start_codex: null,
    });
    expect(draft).toEqual({
      subscription_cost_claude: "20", subscription_cost_codex: "", hourly_rate: "35",
      subscription_start_claude: "2026-07-18", subscription_start_codex: "",
    });
    expect(roiPayload(draft)).toEqual({
      subscription_cost_claude: 20, subscription_cost_codex: null, hourly_rate: 35,
      subscription_start_claude: "2026-07-18", subscription_start_codex: null,
    });
  });

  it("plansWithData: solo planes de fuentes con datos", () => {
    const st = (key: SourceStatus["key"], state: SourceStatus["state"]) => ({ key, label: key, state, detail: "" });
    expect(plansWithData([st("claude_code", "data"), st("codex", "empty"), st("hermes", "data")])).toEqual(["claude"]);
    expect(plansWithData([st("claude_code", "empty"), st("codex", "data")])).toEqual(["codex"]);
    expect(plansWithData([])).toEqual([]);
  });
});
```

En `frontend/src/lib/settings.test.ts`, importa `projectPaths` junto a `sourceStatuses` y añade:

```ts
describe("projectPaths", () => {
  it("une los proyectos de las cuatro fuentes por proyecto, sin OpenRouter, ordenados y sin duplicar", () => {
    const sources = {
      claude_code: { "/b": usage, "/a": usage }, codex: { "/a": usage }, opencode: {}, hermes: { "/c": usage },
      openrouter: { unavailable: false, models: { m: { tokens: 1, cost: 1, requests: 1 } } },
    } as UsageSnapshot["sources"];
    expect(projectPaths(sources)).toEqual(["/a", "/b", "/c"]);
    expect(projectPaths(null)).toEqual([]);
  });
});
```

Run: `cd frontend && npx vitest run src/lib/roiDraft.test.ts src/lib/settings.test.ts`
Expected: FAIL (el módulo `@/lib/roiDraft` y `projectPaths` no existen).

- [ ] **Step 2: Implementar `lib/roiDraft.ts` y `projectPaths`**

`frontend/src/lib/roiDraft.ts`:

```ts
import type { RoiSettings } from "@/lib/api";
import type { SourceStatus } from "@/lib/settings";

/** Borrador de formulario: todo como texto; "" = sin valor. */
export type RoiDraft = Record<keyof RoiSettings, string>;
export type RoiPlan = "claude" | "codex";

export function toRoiDraft(s: RoiSettings): RoiDraft {
  return {
    subscription_cost_claude: s.subscription_cost_claude?.toString() ?? "",
    subscription_cost_codex: s.subscription_cost_codex?.toString() ?? "",
    hourly_rate: s.hourly_rate?.toString() ?? "",
    subscription_start_claude: s.subscription_start_claude ?? "",
    subscription_start_codex: s.subscription_start_codex ?? "",
  };
}

export function roiPayload(d: RoiDraft): Partial<RoiSettings> {
  return {
    subscription_cost_claude: d.subscription_cost_claude ? Number(d.subscription_cost_claude) : null,
    subscription_cost_codex: d.subscription_cost_codex ? Number(d.subscription_cost_codex) : null,
    hourly_rate: d.hourly_rate ? Number(d.hourly_rate) : null,
    subscription_start_claude: d.subscription_start_claude || null,
    subscription_start_codex: d.subscription_start_codex || null,
  };
}

/** Planes con suscripción que tiene sentido pedir: los de fuentes con datos. */
export function plansWithData(statuses: SourceStatus[]): RoiPlan[] {
  const withData = new Set(statuses.filter((s) => s.state === "data").map((s) => s.key));
  return (["claude", "codex"] as const).filter((plan) => withData.has(plan === "claude" ? "claude_code" : "codex"));
}
```

En `lib/settings.ts`, exporta:

```ts
/** Rutas de proyecto de las fuentes por proyecto (sin OpenRouter), ordenadas y sin duplicar. */
export function projectPaths(sources: UsageSnapshot["sources"] | null): string[] {
  if (!sources) return [];
  return [...new Set(PROJECT_SOURCES.flatMap((key) => Object.keys(sources[key] ?? {})))].sort();
}
```

- [ ] **Step 3: Extraer `RoiFields` y adaptar `SettingsForm`**

`frontend/src/components/RoiFields.tsx`:

```tsx
import type { RoiDraft, RoiPlan } from "@/lib/roiDraft";

interface RoiFieldsProps {
  draft: RoiDraft;
  onChange: (key: keyof RoiDraft, value: string) => void;
  /** Planes a mostrar; la tarifa por hora aparece siempre. */
  plans?: RoiPlan[];
}

export function RoiFields({ draft, onChange, plans = ["claude", "codex"] }: RoiFieldsProps) {
  const claude = plans.includes("claude");
  const codex = plans.includes("codex");
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {claude && <Field label="Suscripción Claude ($/mes)" value={draft.subscription_cost_claude} onChange={(v) => onChange("subscription_cost_claude", v)} />}
        {codex && <Field label="Suscripción Codex ($/mes)" value={draft.subscription_cost_codex} onChange={(v) => onChange("subscription_cost_codex", v)} />}
        <Field label="Tarifa por hora ($)" value={draft.hourly_rate} onChange={(v) => onChange("hourly_rate", v)} />
      </div>
      {(claude || codex) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {claude && <Field type="date" label="Inicio suscripción Claude" value={draft.subscription_start_claude} onChange={(v) => onChange("subscription_start_claude", v)} />}
          {codex && <Field type="date" label="Inicio suscripción Codex" value={draft.subscription_start_codex} onChange={(v) => onChange("subscription_start_codex", v)} />}
        </div>
      )}
    </>
  );
}

function Field({ label, value, onChange, type = "number" }: {
  label: string; value: string; onChange: (v: string) => void; type?: "number" | "date";
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        type={type}
        {...(type === "number" ? { min: "0", step: "0.01", placeholder: "—" } : {})}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
      />
    </label>
  );
}
```

En `SettingsForm.tsx`:
- borra `type Draft`, `toDraft`, `Field` y el cálculo inline del payload;
- importa `RoiFields`, y `toRoiDraft`, `roiPayload` y `RoiDraft` desde `@/lib/roiDraft`;
- estado: `useState<RoiDraft | null>(null)`;
- carga: `setDraft(toRoiDraft(s))`;
- `const update = (key: keyof RoiDraft, value: string) => setDraft((d) => (d ? { ...d, [key]: value } : d));`;
- en `handleSave`: `setDraft(toRoiDraft(await saveRoiSettings(roiPayload(draft))))`;
- en el JSX, los dos `<div className="grid ...">` de campos se sustituyen por `<RoiFields draft={draft} onChange={update} />`.

El resto del componente (cabecera, botón Guardar, estado) queda igual.

- [ ] **Step 4: Crear `ClientRootsEditor`**

`frontend/src/components/ClientRootsEditor.tsx`:

```tsx
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MAX_CLIENT_ROOTS, previewClients, type ClientRoot, type ClientRootMode } from "@/lib/clients";

const MODE_OPTIONS: { value: ClientRootMode; label: string }[] = [
  { value: "cliente", label: "La carpeta siguiente es el cliente" },
  { value: "plano", label: "Todo lo de dentro es un solo cliente" },
];

interface ClientRootsEditorProps {
  roots: ClientRoot[];
  onChange: (roots: ClientRoot[]) => void;
  /** Rutas de proyecto conocidas, para la vista previa. */
  paths: string[];
}

/** Editor controlado de raíces (nombre de carpeta o ruta absoluta + modo). La primera que coincide gana. */
export function ClientRootsEditor({ roots, onChange, paths }: ClientRootsEditorProps) {
  const set = (i: number, next: Partial<ClientRoot>) => onChange(roots.map((r, j) => (j === i ? { ...r, ...next } : r)));
  const move = (i: number, delta: -1 | 1) => {
    const next = [...roots];
    [next[i], next[i + delta]] = [next[i + delta], next[i]];
    onChange(next);
  };
  const preview = previewClients(paths, roots);

  return (
    <div className="space-y-4">
      <ol className="space-y-2">
        {roots.map((r, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2">
            <input
              aria-label={`Raíz ${i + 1}`}
              value={r.root}
              onChange={(e) => set(i, { root: e.target.value })}
              placeholder="DEV o /ruta/absoluta"
              spellCheck={false}
              className="min-w-0 flex-1 rounded-lg border bg-background px-3 py-2 font-mono text-sm"
            />
            <select
              aria-label={`Modo de la raíz ${i + 1}`}
              value={r.mode}
              onChange={(e) => set(i, { mode: e.target.value as ClientRootMode })}
              className="rounded-lg border bg-background px-2 py-2 text-sm"
            >
              {MODE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <Button variant="ghost" size="icon-sm" aria-label="Subir" disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp aria-hidden /></Button>
            <Button variant="ghost" size="icon-sm" aria-label="Bajar" disabled={i === roots.length - 1} onClick={() => move(i, 1)}><ArrowDown aria-hidden /></Button>
            <Button variant="ghost" size="icon-sm" aria-label="Quitar" disabled={roots.length === 1} onClick={() => onChange(roots.filter((_, j) => j !== i))}><Trash2 aria-hidden /></Button>
          </li>
        ))}
      </ol>
      <Button
        variant="outline"
        size="sm"
        disabled={roots.length >= MAX_CLIENT_ROOTS}
        onClick={() => onChange([...roots, { root: "", mode: "cliente" }])}
      >
        <Plus aria-hidden />Añadir raíz
      </Button>
      <div aria-live="polite" className="rounded-lg border bg-muted/40 p-3 text-sm">
        {paths.length === 0 ? (
          <p className="text-muted-foreground">Aún no hay proyectos detectados; la agrupación se aplicará cuando los haya.</p>
        ) : (
          <>
            <p className="font-medium">Así quedarían tus {paths.length} proyectos:</p>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {preview.clients.map((c) => (
                <li key={c.name} className="rounded-full border px-2 py-0.5 text-xs">{c.name} · {c.count}</li>
              ))}
            </ul>
            {preview.other > 0 && <p className="mt-2 text-xs text-muted-foreground">{preview.other} en «Otros» (no coinciden con ninguna raíz).</p>}
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Crear `ClientRootsForm` y conectar `SettingsView`**

`frontend/src/components/ClientRootsForm.tsx`:

```tsx
import { useState } from "react";
import { AlertCircle, Check, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ClientRootsEditor } from "@/components/ClientRootsEditor";
import { useAppSettings } from "@/hooks/appSettingsContext";
import { errorDetail, saveAppSettings } from "@/lib/api";
import type { ClientRoot } from "@/lib/clients";

export function ClientRootsForm({ paths }: { paths: string[] }) {
  const { roots, reload } = useAppSettings();
  const [draft, setDraft] = useState<ClientRoot[] | null>(null);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const current = draft ?? roots;

  const handleSave = async () => {
    setStatus("saving");
    setError(null);
    try {
      await saveAppSettings({ client_roots: current });
      await reload();
      setDraft(null);
      setStatus("saved");
    } catch (err) {
      setError(errorDetail(err));
      setStatus("error");
    }
  };

  return (
    <section aria-labelledby="roots-title" className="space-y-4 rounded-xl border bg-card p-5">
      <div>
        <h2 id="roots-title" className="text-sm font-medium">Carpetas de clientes</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Cómo se agrupan tus proyectos por cliente. Usa un nombre de carpeta (en cualquier nivel) o una ruta absoluta; gana la primera que coincide.
        </p>
      </div>
      <ClientRootsEditor roots={current} onChange={(next) => { setDraft(next); setStatus("idle"); }} paths={paths} />
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={handleSave} disabled={status === "saving"}><Save aria-hidden />Guardar</Button>
        <span role="status" className="text-sm">
          {status === "saved" && <span className="inline-flex items-center gap-1"><Check className="h-4 w-4" aria-hidden />Cambios guardados</span>}
          {status === "error" && (
            <span className="inline-flex items-center gap-1 text-destructive">
              <AlertCircle className="h-4 w-4" aria-hidden />No se pudo guardar{error ? `: ${error}` : ". Revisa que el servidor siga activo."}
            </span>
          )}
        </span>
      </div>
    </section>
  );
}
```

En `views/SettingsView.tsx`:
- importa `Link` de `react-router-dom`, `RotateCcw` de `lucide-react`, `ClientRootsForm`, `projectPaths` desde `@/lib/settings` y `viewPath` desde `@/lib/routes`;
- sustituye la cabecera `<h1>` por:

```tsx
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Configuración</h1>
        <Link to={viewPath("onboarding")} className="inline-flex items-center gap-1.5 text-sm text-link hover:underline">
          <RotateCcw className="h-4 w-4" aria-hidden />Repetir configuración inicial
        </Link>
      </div>
      <ClientRootsForm paths={projectPaths(sources)} />
```

  El orden queda así: cabecera, `ClientRootsForm`, `SettingsForm`, `EngineSettingsForm`, Fuentes.

- [ ] **Step 6: Verificación del frontend**

Run: `cd frontend && npx vitest run && npx oxlint && npx tsc -b --noEmit && npm run build`
Expected: todo en verde.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): carpetas de clientes en Configuración y campos de ROI reutilizables"
```

---

### Task 8: Vista `/bienvenida` y guarda de onboarding

**Files:**
- Create: `frontend/src/views/OnboardingView.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes:
  - `ClientRootsEditor` y `RoiFields` (Task 7);
  - `toRoiDraft`, `roiPayload`, `plansWithData`, `RoiDraft` (Task 7);
  - `projectPaths` y `sourceStatuses` (`lib/settings.ts`);
  - `suggestRoots`, `suggestBackend`, `saveOnboarding`, `skipDraft`, `ONBOARDING_STEPS`, `shouldRedirectToOnboarding` (Task 5);
  - `useAppSettings` (Task 6);
  - `fetchRoiSettings`, `fetchEngineSettings`, `saveAppSettings`, `saveRoiSettings`, `saveEngineSettings`, `completeOnboarding` (`lib/api.ts`);
  - `BACKEND_OPTIONS`, `parseChain` (`lib/recommendations.ts`).
- Produces: `<OnboardingView sources={...} />`.

La lógica de decisión ya está probada en la Task 5 (`shouldRedirectToOnboarding`, `saveOnboarding`, `skipDraft`, `suggest*`). Esta tarea es de cableado de UI. Su verificación es `tsc`/`build`, más una comprobación manual con Playwright en el Step 4.

- [ ] **Step 1: Crear `OnboardingView`**

`frontend/src/views/OnboardingView.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ClientRootsEditor } from "@/components/ClientRootsEditor";
import { RoiFields } from "@/components/RoiFields";
import { useAppSettings } from "@/hooks/appSettingsContext";
import {
  completeOnboarding, fetchEngineSettings, fetchRoiSettings, saveAppSettings, saveEngineSettings, saveRoiSettings,
  type AvailableBackends, type EngineBackend, type UsageSnapshot,
} from "@/lib/api";
import type { ClientRoot } from "@/lib/clients";
import { ONBOARDING_STEPS, saveOnboarding, skipDraft, suggestBackend, suggestRoots, type OnboardingDraft } from "@/lib/onboarding";
import { BACKEND_OPTIONS, parseChain } from "@/lib/recommendations";
import { plansWithData, roiPayload, toRoiDraft, type RoiDraft } from "@/lib/roiDraft";
import { projectPaths, sourceStatuses } from "@/lib/settings";

const API = { saveAppSettings, saveRoiSettings, saveEngineSettings, completeOnboarding };
const TITLES = { folders: "Carpetas de clientes", roi: "Tu plan", engine: "Motor de recomendaciones" } as const;

interface Loaded {
  roi: RoiDraft;
  backend: EngineBackend;
  chain: string;
  available: AvailableBackends;
}

export function OnboardingView({ sources }: { sources: UsageSnapshot["sources"] | null }) {
  const navigate = useNavigate();
  const { roots: savedRoots, completedAt, reload } = useAppSettings();
  const firstTime = completedAt === null;
  const paths = projectPaths(sources);
  const statuses = sourceStatuses(sources);

  const [step, setStep] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [roots, setRoots] = useState<ClientRoot[] | null>(firstTime ? null : savedRoots);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchRoiSettings(), fetchEngineSettings()])
      .then(([roi, engine]) => setLoaded({
        roi: toRoiDraft(roi),
        backend: firstTime ? suggestBackend(engine.available) : engine.backend,
        chain: engine.llm_chain.join("\n"),
        available: engine.available,
      }))
      .catch((err: Error) => setLoadError(err.message));
  }, [firstTime]);

  // Primera vez: la sugerencia se calcula cuando llega el snapshot con proyectos.
  // `roots === null` indica que el usuario aún no ha tocado las raíces.
  const effectiveRoots = roots ?? (sources ? suggestRoots(paths) : null);

  const finish = async (draft: OnboardingDraft) => {
    setSaving(true);
    setSaveError(null);
    const result = await saveOnboarding(draft, API);
    setSaving(false);
    if (!result.ok) {
      setStep(ONBOARDING_STEPS.indexOf(result.step));
      setSaveError(result.message);
      return;
    }
    await reload();
    navigate("/", { replace: true });
  };

  if (loadError) {
    return (
      <Shell>
        <div role="alert" className="flex items-center gap-2 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
          No se pudo cargar la configuración ({loadError}). Revisa que el servidor siga activo.
        </div>
      </Shell>
    );
  }
  if (!loaded || !effectiveRoots) return <Shell><Skeleton className="h-72 w-full rounded-xl" /></Shell>;

  const current = ONBOARDING_STEPS[step];
  const plans = plansWithData(statuses);
  const draft: OnboardingDraft = {
    roots: effectiveRoots,
    roi: roiPayload(loaded.roi),
    engine: { backend: loaded.backend, llm_chain: parseChain(loaded.chain) },
  };

  return (
    <Shell>
      <header className="space-y-1">
        <p className="text-xs text-muted-foreground">Paso {step + 1} de {ONBOARDING_STEPS.length}</p>
        <h1 className="text-xl font-semibold">{TITLES[current]}</h1>
      </header>

      {current === "folders" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Indica en qué carpeta guardas los proyectos de cada cliente. Con «La carpeta siguiente es el cliente», en <code>~/DEV/ACME/app</code> el cliente es ACME.
          </p>
          <SourcesSummary statuses={statuses} />
          <ClientRootsEditor roots={effectiveRoots} onChange={setRoots} paths={paths} />
        </div>
      )}

      {current === "roi" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {plans.length > 0
              ? "Con el costo de tu suscripción el dashboard la compara contra el precio de la API. Puedes dejarlo vacío y completarlo después."
              : "Aún no hay datos de Claude Code ni de Codex; podrás indicar tu suscripción en Configuración cuando los haya."}
          </p>
          <RoiFields draft={loaded.roi} plans={plans} onChange={(key, value) => setLoaded({ ...loaded, roi: { ...loaded.roi, [key]: value } })} />
        </div>
      )}

      {current === "engine" && (
        <fieldset className="space-y-2">
          <legend className="text-sm text-muted-foreground">Qué modelo redacta las recomendaciones. Puedes cambiarlo en Configuración.</legend>
          {BACKEND_OPTIONS.map((option) => {
            const installed = option.value === "none" || loaded.available[option.value];
            return (
              <label key={option.value} className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="onboarding-backend"
                  value={option.value}
                  checked={loaded.backend === option.value}
                  disabled={!installed}
                  onChange={() => setLoaded({ ...loaded, backend: option.value })}
                  className="mt-1"
                />
                <span className={installed ? "" : "opacity-60"}>
                  <span className="font-medium">{option.label}</span>
                  <span className="block text-xs text-muted-foreground">
                    {installed ? option.hint : `No se encontró «${option.value}» en el PATH del servidor. Instálalo y vuelve a esta pantalla desde Configuración.`}
                  </span>
                </span>
              </label>
            );
          })}
        </fieldset>
      )}

      {saveError && (
        <p role="alert" className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden />{saveError}
        </p>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
        <Button variant="ghost" disabled={saving} onClick={() => finish(skipDraft(loaded.available, parseChain(loaded.chain)))}>
          Omitir
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" disabled={saving || step === 0} onClick={() => setStep(step - 1)}>Atrás</Button>
          {step < ONBOARDING_STEPS.length - 1 ? (
            <Button disabled={saving} onClick={() => { setSaveError(null); setStep(step + 1); }}>Siguiente</Button>
          ) : (
            <Button disabled={saving} onClick={() => finish(draft)}>{saving ? "Guardando…" : "Finalizar"}</Button>
          )}
        </div>
      </footer>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-svh items-start justify-center bg-background p-4 text-foreground md:items-center md:p-8">
      <div className="w-full max-w-2xl space-y-6 rounded-xl border bg-card p-5 md:p-8">
        <p className="font-mono text-xs text-muted-foreground">ai-monitor · configuración inicial</p>
        {children}
      </div>
    </main>
  );
}

function SourcesSummary({ statuses }: { statuses: ReturnType<typeof sourceStatuses> }) {
  if (statuses.length === 0) return <Skeleton className="h-6 w-full" />;
  return (
    <ul className="flex flex-wrap gap-1.5 text-xs">
      {statuses.map((s) => (
        <li key={s.key} className="rounded-full border px-2 py-0.5">
          {s.label}: {s.state === "data" ? s.detail : "sin datos"}
        </li>
      ))}
    </ul>
  );
}
```

Si `tsc` marca `React.ReactNode`, cámbialo por `import type { ReactNode } from "react"` y usa `ReactNode`.

- [ ] **Step 2: Guarda y ruta en `App.tsx`**

Importa `useLocation` de `react-router-dom`, `useAppSettings` desde `@/hooks/appSettingsContext`, `shouldRedirectToOnboarding` desde `@/lib/onboarding` y `OnboardingView` desde `@/views/OnboardingView`. Junto a los demás hooks, **antes** de cualquier `return`:

```tsx
  const appSettings = useAppSettings();
  const { pathname } = useLocation();
```

Añade estas líneas justo después de `if (!route.valid) return <Navigate to="/" replace />;`:

```tsx
  if (appSettings.loading) return <div className="min-h-svh bg-background" aria-busy="true" />;
  if (shouldRedirectToOnboarding(appSettings, pathname)) return <Navigate to="/bienvenida" replace />;
  if (route.view === "onboarding") return <OnboardingView sources={sources} />;
```

(`appSettings` cumple `OnboardingGate` porque tiene `loading`, `error`, `degraded` y `completedAt`.)

- [ ] **Step 3: Verificación del frontend**

Run: `cd frontend && npx vitest run && npx oxlint && npx tsc -b --noEmit && npm run build`
Expected: todo en verde.

- [ ] **Step 4: Comprobación manual con Playwright contra una BD temporal**

**No uses** `~/.local/share/ai-monitor/history.db` ni el server de systemd (puerto 8420). `build_app` recolecta con `main.collect_all()` sin `db_path`, así que el script lo envuelve para que también escriba en la BD temporal. Guárdalo en el scratchpad como `onboarding_server.py`:

```python
import os, sys, tempfile
sys.path.insert(0, os.getcwd())
import main, server

db = os.path.join(tempfile.mkdtemp(), "history.db")
_orig = main.collect_all
server.main.collect_all = lambda db_path=None: _orig(db_path=db)
httpd = server.build_app("frontend/dist", poll_interval_seconds=3600, port=8431, db_path=db)
print("BD temporal:", db, flush=True)
httpd.serve_forever()
```

Run (desde la raíz del repo, en segundo plano): `python3 <scratchpad>/onboarding_server.py`

Después, con Playwright CLI (`npx playwright` desde `frontend/`, instalándolo con `npm install -D playwright` si falta), comprueba:
1. `http://127.0.0.1:8431/` redirige a `/bienvenida`.
2. Omitir → vuelve a `/`, y recargar ya no redirige.
3. `/configuracion` → "Repetir configuración inicial" abre `/bienvenida` con las raíces actuales.
4. En el paso 1, cambiar la raíz actualiza la vista previa.

Anota en el commit o en el reporte de la tarea el resultado de cada punto. Detén el server al terminar.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): onboarding /bienvenida con carpetas, plan y motor"
```

---

### Task 9: Documentación

**Files:**
- Modify: `README.md` (nueva sección después de "Dashboard interactivo (opcional)"), `CLAUDE.md` (sección Architecture)

- [ ] **Step 1: README: sección "Configuración inicial"**

Inserta antes de `### Estructura del dashboard`:

````markdown
### Configuración inicial

La primera vez que abres el dashboard aparece `/bienvenida`, con tres pasos:

1. **Carpetas de clientes**: cómo se agrupan tus proyectos. Cada raíz es un nombre de carpeta
   (coincide en cualquier nivel, sin distinguir mayúsculas) o una ruta absoluta (coincide por
   prefijo). Hay dos modos:
   - *La carpeta siguiente es el cliente* (`cliente`): con la raíz `DEV`, `~/DEV/ACME/app` → cliente `ACME`.
   - *Todo lo de dentro es un solo cliente* (`plano`): con la raíz `/srv/trabajo`, `/srv/trabajo/api` → cliente `trabajo`.

   Gana la primera raíz que coincide; lo que no coincide con ninguna va a «Otros». Por defecto:
   `DEV` en modo `cliente`.
2. **Tu plan**: costo y fecha de inicio de las suscripciones. Solo se piden las fuentes con datos.
3. **Motor de recomendaciones**: Hermes, `claude -p` o ninguno. Las opciones que no están en el
   `PATH` del servidor aparecen deshabilitadas. Si no tienes ninguna, el motor funciona solo con
   reglas locales.

«Omitir» guarda los valores por defecto (raíces `DEV`, backend sugerido) y no vuelve a mostrar
la pantalla. Para repetirla: Configuración → «Repetir configuración inicial». Los ajustes se
guardan en la tabla `app_settings` de `history.db`.

En un equipo sin Claude Code, Codex, OpenCode ni Hermes, el dashboard arranca vacío y el
onboarding funciona igual: las fuentes aparecen «sin datos» y el motor queda en «Ninguno».
````

- [ ] **Step 2: CLAUDE.md**

En la viñeta de `briefing.py`, sustituye `client_of` portado de `lib/clients.ts` con casos compartidos en `tests/fixtures/client_of_cases.json` por: `client_of` delega en `clients.py` con las raíces leídas en solo lectura de `app_settings`.

Añade una viñeta nueva después de la de `history.py`:

```markdown
- **`clients.py`** es la única implementación de `client_of(path, roots)` en el backend; `frontend/src/lib/clients.ts` es su port, y `tests/fixtures/client_of_cases.json` es el contrato entre ambos (cada caso lleva `roots`, `null` = por defecto). Si cambias la regla de un lado, cambia el otro y añade el caso al fixture. Las raíces (`client_roots`) y la marca `onboarding_completed_at` viven en la tabla `app_settings` de `history.db` (`history.get/save_app_settings`, `complete_onboarding`); la única vía de escritura es `/api/app-settings`.
```

En la viñeta de `frontend/`, añade `/api/app-settings` a la lista de endpoints.

- [ ] **Step 3: Verificación de portabilidad**

Run: `git grep -n "jruedadev\|DEV/JRDV" -- ':!docs/external_context' || echo limpio`
Expected: `limpio`. Si aparecen coincidencias en `docs/superpowers/`, revisa si son previas a este plan (`git log -S`); este plan no debe añadir ninguna.

- [ ] **Step 4: Verificación completa final**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests && cd frontend && npx vitest run && npx oxlint && npx tsc -b --noEmit && npm run build`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: configuración inicial, raíces de cliente y contrato client_of"
```
