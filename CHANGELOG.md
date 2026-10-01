# Changelog

Todos los cambios relevantes de este proyecto se documentan aquí. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Semantic Versioning](https://semver.org/lang/es/). La política de versionado está en `AGENTS.md`.

## [Sin publicar]

### Añadido
- Actividad en vivo de Claude Code, OpenCode y Hermes: nuevo endpoint `GET /api/activity` y evento `activity` en `/api/stream` (estado por sesión: pensando, usando una herramienta, esperando o en pausa; sin textos ni argumentos).

### Corregido
- Las fechas de las sesiones de OpenCode: la última actividad es la real (antes mostraba el inicio de la sesión) y las duraciones se calculan bien.

## [1.0.0] - 2026-09-29

Primera versión estable.

### Añadido
- Colectores aislados para Claude Code, Codex, OpenCode, Hermes Agent y OpenRouter. Una fuente ausente se omite sin romper el dashboard.
- `history.db` (SQLite) con rollups diarios que conservan el histórico más allá de la retención de cada proveedor, y la tabla de precios gestionada con `collectors/sync_pricing.py`.
- CLI `main.py` con tabla combinada, `--json`, `--html` y `--briefing`.
- `server.py` con API en vivo y SSE, y el frontend (Vite, React, TypeScript, shadcn/ui) con las vistas Inicio, Actividad, Gasto y ROI, Proyectos, Recomendaciones y Configuración.
- Motor de recomendaciones: lectura y redacción local de prompts, clustering, LLM opcional (Hermes free o `claude -p`) con heurística de respaldo, señales de costo y timer diario de systemd.
- Raíces de cliente configurables (modos `cliente` y `plano`) y onboarding en `/bienvenida`.

[Sin publicar]: https://github.com/jruedadev/ai-monitor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/jruedadev/ai-monitor/releases/tag/v1.0.0
