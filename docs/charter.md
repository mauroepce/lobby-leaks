# LobbyLeaks – Project Charter

## Propósito

Empoderar a la ciudadanía mundial, empezando por **Chile**, poniendo en
un grafo abierto la relación entre lobby oficial, gasto parlamentario y
financiamiento electoral antes de procesos electorales.

## Alcance

- **Módulo Chile**: ingestión automática vía API Ley de Lobby, Transparencia
  Activa y Servel.
- **Modo global**: arquitectura multi‑jurisdicción; cualquier país puede
  añadir un conector o subir evidencia manual (“Sube tu leak”).
- Exponerlos mediante API abierta, UI web y descargas CSV/JSON.
- Entregar un MVP funcional en 8 semanas (31 ago 2025).

## Fuera de alcance

- Reportajes de opinión o investigación editorial.
- Scraping de redes sociales en tiempo real.
- Carga de datos privados o con copyright restrictivo.

## Métricas de éxito

| KPI | Fórmula ⚙️ | Línea base <br>25 jun 2025 | Meta <br>+8 semanas | Fuente de medición | Revisión |
|-----|------------|---------------------------|---------------------|--------------------|----------|
| **Países integrados** | `jurisdictions.count()` | 1 (CL) | ≥ 2 | DB stats | Cada sprint |
| **Éxito de ingesta diaria** | `jobs_ok / jobs_tot` | 0 / 0 | ≥ 95 % | Cron monitor (StatusCake) | Cada semana |
| **Visitantes únicos / semana** | Matomo `Visits > Unique` | 0 | ≥ 500 | Matomo | Cada lunes |
| **PRs de la comunidad fusionadas** | `PR_merged_community` | 0 | ≥ 3 | GitHub API | Fin de sprint |
| **Tiempo mediano de proceso PDF ciudadano** | p50 `end-to-end_secs` | — | ≤ 900 s | CloudWatch (λ OCR) | Cada despliegue |
| **Alertas lobby ↔ aporte emitidas** | `alerts_sent` | 0 | ≥ 20 | Supabase Realtime | Cada sprint |
> *Fuentes de datos*: Matomo v5 (analytics), GitHub REST v3, Supabase Metrics, StatusCake Cron.  
> *Cadencia de revisión*: los KPIs se comentan cada sprint (viernes) y se publican en `/docs/kpi-history.md`.

## Roadmap

Resumen visual del plan de 8 semanas en `/docs/roadmap.png` (auto-generado desde GitHub Projects).

_Licencia MIT · última edición 25 jun 2026_
