# AGENTS.md

Directivas para cualquier agente (Claude Code, Codex, OpenCode, Hermes…) que trabaje en este
repositorio. La arquitectura y las restricciones técnicas están en `CLAUDE.md`; léelo antes de
tocar código. Este archivo fija cómo se versiona y cómo se planifica cada cambio.

## Versionado semántico

El proyecto sigue [Semantic Versioning 2.0.0](https://semver.org/lang/es/): `MAJOR.MINOR.PATCH`.

### Fuente única de la versión

- `VERSION` (raíz del repo) es la fuente de verdad: una sola línea `X.Y.Z`.
- `frontend/package.json` y `frontend/package-lock.json` llevan la misma versión. Actualízalos
  con `npm version X.Y.Z --no-git-tag-version` dentro de `frontend/`, nunca a mano.
- `CHANGELOG.md` (formato Keep a Changelog, en español) tiene siempre una sección
  `## [Sin publicar]` arriba y una sección `## [X.Y.Z] - AAAA-MM-DD` por versión publicada.
- `tests/test_version.py` falla si estos tres se desincronizan.

### Qué es la API pública

SemVer se mide contra lo que un usuario o un script ya instalado puede romper al actualizar:

1. **CLI:** flags y salida de `main.py` (`--json`, `--html`, `--briefing`) y de `python3 -m recommend`.
2. **HTTP:** rutas `/api/*` de `server.py` y la forma de sus respuestas y del evento SSE.
3. **Datos persistidos:** el esquema de `history.db` (tablas, columnas, claves de ajustes)
   y su contenido. Los usuarios acumulan histórico que no pueden regenerar.
4. **Configuración e instalación:** `~/.config/ai-monitor/env`, variables de entorno
   (`OPENROUTER_API_KEY`, `AI_MONITOR_PORT`), `install.sh`, `shell/aliases.sh` y las unidades
   de `systemd/`.
5. **URLs del dashboard:** rutas y parámetros de query que un usuario puede tener guardados.

El código interno (módulos, funciones, componentes) no es API pública.

### Cómo se elige el incremento

| Incremento | Cuándo | Ejemplos en este repo |
|---|---|---|
| **MAJOR** | Un usuario que actualiza pierde algo o tiene que intervenir a mano | quitar o renombrar un endpoint o flag; cambiar la forma de una respuesta existente; migración de `history.db` que borra o reinterpreta datos; quitar una URL sin redirección; cambiar el formato de `~/.config/ai-monitor/env` |
| **MINOR** | Funcionalidad nueva compatible hacia atrás | nueva vista, endpoint, flag, fuente o colector; tabla o columna nueva con migración aditiva; URL renombrada con redirección desde la antigua |
| **PATCH** | Corrección compatible sin funcionalidad nueva | bug fix; mejora de rendimiento; corrección de cálculo de costo; ajuste visual |
| *(ninguno)* | No llega al usuario | solo docs, tests, refactor interno, specs y planes |

Ante la duda entre dos niveles, elige el mayor. Un cambio de esquema de `history.db` nunca es
PATCH: es MINOR si es aditivo y MAJOR si no lo es (y recuerda que `history.db` nunca se poda,
ver `CLAUDE.md`).

### Commits

Los commits siguen Conventional Commits y alimentan la decisión de versión:

- `feat:` → MINOR · `fix:` / `perf:` → PATCH · `docs:` / `test:` / `refactor:` / `chore:` → sin versión.
- Un cambio incompatible lleva `!` tras el tipo (`feat(server)!: …`) y un pie
  `BREAKING CHANGE: <qué se rompe y cómo migrar>` → MAJOR.
- Nunca incluyas `Co-Authored-By: Claude` ni líneas `Claude-Session:`.

### Changelog

Cada commit `feat`, `fix`, `perf` o incompatible añade una línea a `## [Sin publicar]` en la
subsección que toque (`Añadido`, `Cambiado`, `Obsoleto`, `Eliminado`, `Corregido`, `Seguridad`),
escrita para el usuario, no para el desarrollador. Los cambios incompatibles explican la
migración.

### Publicar una versión

Una versión se corta cuando termina una spec (al cerrar su plan) o cuando el usuario lo pide
para acumular correcciones sueltas:

1. Decide el incremento a partir de `## [Sin publicar]` y de la tabla anterior.
2. Actualiza `VERSION` y `frontend/` (`npm version X.Y.Z --no-git-tag-version`).
3. En `CHANGELOG.md`, renombra `## [Sin publicar]` a `## [X.Y.Z] - AAAA-MM-DD`, abre un
   `## [Sin publicar]` vacío encima y actualiza los enlaces de comparación al final.
4. Corre la suite completa (backend y frontend) y haz commit: `chore(release): vX.Y.Z`.
5. **Con permiso del usuario**, y solo entonces: tag anotado `git tag -a vX.Y.Z -m "ai-monitor X.Y.Z"`,
   push del tag y release en GitHub (`gh release create vX.Y.Z --verify-tag`) con las notas de
   esa sección del changelog. Push, tags y releases son acciones hacia fuera: nunca sin permiso.

Los tags son siempre `vX.Y.Z`. Las preversiones usan `vX.Y.Z-rc.N` y se marcan `--prerelease`.

## Specs y planes

Las specs (`docs/superpowers/specs/`) y los planes (`docs/superpowers/plans/`) se adaptan al
versionado así:

### En cada spec

Justo después de la línea `Fecha:`, añade:

```markdown
Versión objetivo: X.Y.Z (MAJOR | MINOR | PATCH) — desde A.B.C
```

e incluye una sección **"Impacto de versión"** que diga:

- Qué partes de la API pública (lista de arriba) toca la spec y si el cambio es aditivo o incompatible.
- Por qué el incremento elegido es el correcto según la tabla.
- Si es MAJOR: qué se rompe, cómo migra un usuario existente y si hay migración automática de
  `history.db` o de la configuración.

La versión de partida es el contenido de `VERSION` al escribir la spec. Si otra versión se
publica antes de implementarla, la versión objetivo se recalcula al empezar el plan.

### En cada plan

- La cabecera lleva, junto a `**Spec:**`, la línea `**Versión:** X.Y.Z (MAJOR | MINOR | PATCH)`,
  copiada de la spec.
- Los mensajes de commit de cada tarea usan el tipo coherente con el incremento: una spec MINOR no
  debe tener commits `!`, y una spec PATCH no debe tener commits `feat:`. Si aparece uno, el plan
  está mal: corrige el incremento en spec y plan antes de seguir.
- Cada tarea que añade o corrige algo visible para el usuario añade su línea a
  `## [Sin publicar]` de `CHANGELOG.md` en su propio commit.
- La **última tarea** del plan es siempre "Release vX.Y.Z" con los pasos 1 a 4 de
  "Publicar una versión" y la suite completa como verificación. Los pasos del punto 5 (tag, push y
  release en GitHub) se dejan fuera del plan y se piden al usuario al terminar la rama.
- Si la spec es MAJOR, el plan incluye una tarea con un test que reproduce la actualización
  desde la versión anterior (por ejemplo, un `history.db` con el esquema viejo) y verifica la
  migración.
